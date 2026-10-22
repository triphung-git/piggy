"""Release guards and updater manifest generation; no publishing side effects."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
UPDATER_PATTERNS = {
    "windows-x86_64": "*.exe.sig",
    "darwin-aarch64": "*.app.tar.gz.sig",
    "linux-x86_64": "*.AppImage.sig",
}


def version_from_tag(tag: str) -> str:
    match = re.fullmatch(
        r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", tag,
    )
    if not match or len(tag) > 200:
        raise ValueError("Release tag must be vMAJOR.MINOR.PATCH, optionally with SemVer prerelease/build identifiers")
    prerelease = match.group(4)
    if prerelease and any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease.split(".")):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeroes")
    return tag[1:]


def decode_public_key(encoded: str) -> bytes:
    try:
        data = base64.b64decode(encoded.strip(), validate=True)
        lines = data.decode("utf-8").splitlines()
        key = base64.b64decode(lines[1], validate=True)
        if not lines[0].startswith("untrusted comment:") or len(key) != 42 or key[:2] != b"Ed":
            raise ValueError("Invalid public key structure")
        return data
    except (ValueError, IndexError, UnicodeError) as exc:
        raise ValueError("Updater pubkey must be a valid Tauri/Minisign public key") from exc


def validate_versions(tag: str, repository: str, read: Callable[[str], str]) -> dict:
    version = version_from_tag(tag)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected GitHub repository owner/name")
    config = json.loads(read("src-tauri/tauri.conf.json"))
    versions = {
        "src-tauri/tauri.conf.json": config["version"],
        "src-tauri/Cargo.toml": tomllib.loads(read("src-tauri/Cargo.toml"))["package"]["version"],
        "pyproject.toml": tomllib.loads(read("pyproject.toml"))["project"]["version"],
        "package.json": json.loads(read("package.json"))["version"],
        "Web Overlay/package.json": json.loads(read("Web Overlay/package.json"))["version"],
    }
    for name in ("package-lock.json", "Web Overlay/package-lock.json"):
        lock = json.loads(read(name))
        versions[name] = lock["version"]
        versions[f"{name} packages[root]"] = lock["packages"][""]["version"]
    mismatched = [name for name, actual in versions.items() if actual != version]
    if mismatched:
        raise ValueError(f"Tag {tag} does not match version in: {', '.join(mismatched)}")
    if config["bundle"].get("createUpdaterArtifacts") is not True:
        raise ValueError("Signed Tauri v2 updater artifacts must be enabled")
    updater = config["plugins"]["updater"]
    expected = f"https://github.com/{repository}/releases/latest/download/latest.json"
    if updater.get("endpoints") != [expected]:
        raise ValueError("Updater endpoint does not match the release repository")
    decode_public_key(updater["pubkey"])
    return config


def git(*arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def preflight(tag: str, repository: str) -> dict[str, str]:
    version_from_tag(tag)  # Validate before using the ref in any Git command.
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Manual Release must run from the main workflow branch")
    sha = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    git("merge-base", "--is-ancestor", sha, "origin/main")
    validate_versions(tag, repository, lambda name: git("show", f"{sha}:{name}"))
    if not os.environ.get("TAURI_SIGNING_PRIVATE_KEY", "").strip():
        raise ValueError("Repository secret TAURI_SIGNING_PRIVATE_KEY is required; unsigned releases are blocked")
    return {"tag": tag, "version": tag[1:], "sha": sha, "prerelease": str("-" in tag[1:].split("+", 1)[0]).lower()}


def verify_signature(binary: Path, signature: str, pubkey: str) -> None:
    """Delegate cryptographic verification to the reference Minisign tool."""
    try:
        decoded = base64.b64decode(signature, validate=True)
        if not decoded.startswith(b"untrusted comment:"):
            raise ValueError("Invalid signature structure")
    except ValueError as exc:
        raise ValueError(f"Invalid Tauri signature for {binary.name}") from exc
    with tempfile.TemporaryDirectory(prefix="tft-verify-") as directory:
        public_file = Path(directory) / "updater.pub"
        signature_file = Path(directory) / "artifact.minisig"
        public_file.write_bytes(decode_public_key(pubkey))
        signature_file.write_bytes(decoded)
        subprocess.run(["minisign", "-V", "-m", str(binary.resolve()), "-p", str(public_file),
                        "-x", str(signature_file)], check=True, capture_output=True, timeout=120)


def signing_probe(ref: str) -> None:
    """Exercise the release CLI and prove the secret matches the release public key."""
    config = json.loads(git("show", f"{ref}:src-tauri/tauri.conf.json"))
    if not os.environ.get("TAURI_SIGNING_PRIVATE_KEY", "").strip():
        raise ValueError("Repository secret TAURI_SIGNING_PRIVATE_KEY is required")
    # Invoke the locked CLI directly: no shell, no secret values in arguments/logs.
    cli = ROOT / "node_modules" / "@tauri-apps" / "cli" / "tauri.js"
    with tempfile.TemporaryDirectory(prefix="tft-signing-probe-") as directory:
        probe = Path(directory) / "signing-probe.txt"
        probe.write_text("TFT Studio release signing preflight\n", encoding="utf-8")
        try:
            subprocess.run(["node", str(cli), "signer", "sign", str(probe)],
                           cwd=ROOT, check=True, capture_output=True, timeout=60,
                           env={**os.environ, "CI": "true",
                                "TAURI_SIGNING_PRIVATE_KEY_PASSWORD": os.environ.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", "")})
        except (OSError, subprocess.SubprocessError):
            raise ValueError("Signing probe failed: check private key format, password and secret scope; CLI output withheld") from None
        try:
            signature = probe.with_suffix(".txt.sig").read_text(encoding="utf-8").strip()
            verify_signature(probe, signature, config["plugins"]["updater"]["pubkey"])
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ValueError("Signing probe verification failed: signing key must match the release updater public key") from None
    print("Signing probe passed: key/password decoded and signature matches release public key")


def make_manifest(assets: Path, tag: str, repository: str, config: dict,
                  verify: Callable = verify_signature) -> dict:
    version = version_from_tag(tag)
    platforms = {}
    for target, pattern in UPDATER_PATTERNS.items():
        candidates = sorted(assets.glob(pattern))
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one signed updater bundle for {target}; found {len(candidates)}")
        signature_path = candidates[0]
        binary = signature_path.with_suffix("")
        if not binary.is_file() or binary.stat().st_size == 0:
            raise ValueError(f"Missing or empty bundle: {binary.name}")
        signature = signature_path.read_text(encoding="utf-8").strip()
        verify(binary, signature, config["plugins"]["updater"]["pubkey"])
        platforms[target] = {
            "url": f"https://github.com/{repository}/releases/download/{quote(tag, safe='')}/{quote(binary.name, safe='')}",
            "signature": signature,
        }
    # Also verify signatures of optional installers such as MSI.
    selected = {next(iter(assets.glob(pattern))) for pattern in UPDATER_PATTERNS.values()}
    for signature_path in sorted(set(assets.glob("*.sig")) - selected):
        binary = signature_path.with_suffix("")
        if not binary.is_file():
            raise ValueError(f"Missing bundle for {signature_path.name}")
        verify(binary, signature_path.read_text(encoding="utf-8").strip(), config["plugins"]["updater"]["pubkey"])
    return {"version": version, "notes": f"TFT Post-Match Studio {tag}",
            "pub_date": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "platforms": platforms}


def generate_checksums(assets: Path) -> Path:
    """Generate SHA256SUMS file for all files in the assets directory."""
    assets = Path(assets)
    lines = []
    for item in sorted(assets.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS":
            digest = hashlib.sha256(item.read_bytes()).hexdigest()
            lines.append(f"{digest}  {item.name}\n")
    checksums_file = assets / "SHA256SUMS"
    checksums_file.write_text("".join(lines), encoding="utf-8")
    return checksums_file


def smoke_sidecar(timeout: float = 30.0, log_dir: Path | None = None, resource_dir: Path | None = None) -> None:
    target = os.environ.get("TARGET", "")
    machine = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    if not target or target.split("-", 1)[0] != machine:
        raise ValueError("Sidecar target architecture must match the Python runner; PyInstaller cannot cross-compile")
    binary = ROOT / "src-tauri" / "binaries" / f"tft-backend-{target}{'.exe' if sys.platform == 'win32' else ''}"
    cmd = [sys.executable, str(ROOT / "scripts" / "smoke_sidecar.py"), "--binary", str(binary), "--timeout", str(timeout)]
    if log_dir:
        cmd.extend(["--log-dir", str(log_dir)])
    if resource_dir:
        cmd.extend(["--resource-dir", str(resource_dir)])
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "signing-probe", "check-version", "manifest", "smoke-sidecar"])
    parser.add_argument("--ref", default="HEAD", help="Validated release commit for signing probe")
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG", ""))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--assets", type=Path, default=Path("release-assets"))
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds")
    parser.add_argument("--log-dir", type=Path, default=None, help="Directory for diagnostic logs")
    parser.add_argument("--resource-dir", type=Path, default=None, help="Explicit resource directory")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            outputs = preflight(args.tag, args.repository)
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
                for key, value in outputs.items():
                    output.write(f"{key}={value}\n")
            print(f"Release preflight passed: {outputs['tag']} at {outputs['sha']}")
        elif args.command == "signing-probe":
            signing_probe(args.ref)
        elif args.command == "check-version":
            validate_versions(args.tag, args.repository, lambda name: (ROOT / name).read_text(encoding="utf-8"))
            print(f"Version and updater configuration match {args.tag}")
        elif args.command == "manifest":
            config = validate_versions(args.tag, args.repository, lambda name: (ROOT / name).read_text(encoding="utf-8"))
            manifest = make_manifest(args.assets, args.tag, args.repository, config)
            (args.assets / "latest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            checksums_file = generate_checksums(args.assets)
            print(f"Verified all signatures, generated latest.json and {checksums_file.name}")
        else:
            smoke_sidecar(timeout=args.timeout, log_dir=args.log_dir, resource_dir=args.resource_dir)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Release blocked: {exc}\n")


if __name__ == "__main__":
    main()
