"""Release validation rejects mismatched refs, versions and incomplete updates."""

import base64
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import release_tools

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "triphung-git/piggy"
TAG = "v" + json.loads((ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["version"]


@pytest.mark.parametrize("tag", ["main", "v01.0.0", "v1.0", "v1.0.0-01", "v1.0.0$(id)", "v1.0.0\nextra"])
def test_rejects_invalid_tags(tag):
    with pytest.raises(ValueError):
        release_tools.version_from_tag(tag)


@pytest.mark.parametrize("tag", ["v1.0.0", "v1.0.1-rc.1", "v2.0.0+build.17"])
def test_accepts_semver_tags(tag):
    assert release_tools.version_from_tag(tag) == tag[1:]


def read_manifest(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_current_manifests_are_consistent():
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    release_tools.validate_versions(f"v{config['version']}", REPOSITORY, read_manifest)


def test_lockfile_version_drift_blocks_release():
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    def altered(name):
        if name == "Web Overlay/package-lock.json":
            data = json.loads(read_manifest(name))
            data["packages"][""]["version"] = "999.0.0"
            return json.dumps(data)
        return read_manifest(name)
    with pytest.raises(ValueError, match="packages"):
        release_tools.validate_versions(f"v{config['version']}", REPOSITORY, altered)


def test_fork_must_update_updater_endpoint():
    with pytest.raises(ValueError, match="endpoint"):
        release_tools.validate_versions(TAG, "different-owner/fork", read_manifest)


def test_unsigned_configuration_is_rejected():
    def altered(name):
        if name == "src-tauri/tauri.conf.json":
            config = json.loads(read_manifest(name))
            config["bundle"]["createUpdaterArtifacts"] = False
            return json.dumps(config)
        return read_manifest(name)
    with pytest.raises(ValueError, match="Signed"):
        release_tools.validate_versions(TAG, REPOSITORY, altered)


def test_preflight_rejects_commit_outside_main(monkeypatch):
    def git(*args):
        if args[0] == "merge-base":
            raise subprocess.CalledProcessError(1, ["git", *args])
        return "a" * 40
    monkeypatch.setattr(release_tools, "git", git)
    with pytest.raises(subprocess.CalledProcessError):
        release_tools.preflight(TAG, REPOSITORY)


def test_preflight_does_not_allow_unsigned_fallback(monkeypatch):
    monkeypatch.setattr(release_tools, "git", lambda *args: read_manifest(args[1].split(":", 1)[1]) if args[0] == "show" else "a" * 40)
    monkeypatch.delenv("TAURI_SIGNING_PRIVATE_KEY", raising=False)
    with pytest.raises(ValueError, match="secret"):
        release_tools.preflight(TAG, REPOSITORY)


def test_manual_workflow_must_run_from_main(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    with pytest.raises(ValueError, match="main"):
        release_tools.preflight(TAG, REPOSITORY)


@pytest.fixture
def bundles(tmp_path):
    for name in ["TFT Studio-setup.exe", "TFT Studio.app.tar.gz", "TFT Studio.AppImage"]:
        (tmp_path / name).write_bytes(b"fixture bundle")
        (tmp_path / f"{name}.sig").write_text("fixture-signature", encoding="utf-8")
    return tmp_path


def test_manifest_is_complete_and_escapes_urls(bundles):
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    verifier = Mock()
    manifest = release_tools.make_manifest(bundles, TAG, REPOSITORY, config, verifier)
    assert set(manifest["platforms"]) == {"windows-x86_64", "darwin-aarch64", "linux-x86_64"}
    assert "%20" in manifest["platforms"]["windows-x86_64"]["url"]
    assert verifier.call_count == 3


def test_missing_platform_blocks_manifest(bundles):
    (bundles / "TFT Studio.AppImage.sig").unlink()
    with pytest.raises(ValueError, match="linux-x86_64"):
        release_tools.make_manifest(bundles, TAG, REPOSITORY, json.loads(read_manifest("src-tauri/tauri.conf.json")), Mock())


def test_duplicate_platform_does_not_pick_arbitrary_bundle(bundles):
    (bundles / "other-setup.exe.sig").write_text("signature", encoding="utf-8")
    with pytest.raises(ValueError, match="windows-x86_64"):
        release_tools.make_manifest(bundles, TAG, REPOSITORY, json.loads(read_manifest("src-tauri/tauri.conf.json")), Mock())


def test_bad_signature_blocks_manifest(bundles):
    verifier = Mock(side_effect=subprocess.CalledProcessError(1, ["minisign"]))
    with pytest.raises(subprocess.CalledProcessError):
        release_tools.make_manifest(bundles, TAG, REPOSITORY, json.loads(read_manifest("src-tauri/tauri.conf.json")), verifier)


def test_optional_rpm_signature_requires_and_verifies_matching_bundle(bundles):
    rpm = bundles / "TFT.Studio-1.0.6-1.x86_64.rpm"
    rpm.with_suffix(".rpm.sig").write_text("rpm-signature", encoding="utf-8")
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    verifier = Mock()
    with pytest.raises(ValueError, match=r"Missing bundle.*rpm\.sig"):
        release_tools.make_manifest(bundles, TAG, REPOSITORY, config, verifier)
    rpm.write_bytes(b"rpm bundle fixture")
    verifier.reset_mock()
    manifest = release_tools.make_manifest(bundles, TAG, REPOSITORY, config, verifier)
    assert verifier.call_count == 4
    assert any(call.args[0] == rpm for call in verifier.call_args_list)
    assert set(manifest["platforms"]) == {"windows-x86_64", "darwin-aarch64", "linux-x86_64"}


def test_tauri_signature_is_decoded_before_reference_verifier(tmp_path, monkeypatch):
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    binary = tmp_path / "bundle.exe"
    binary.write_bytes(b"fixture")
    decoded_signature = b"untrusted comment: test\nfixture\n"
    signature = base64.b64encode(decoded_signature).decode()
    def verify(command, **kwargs):
        assert command[0] == "minisign"
        assert Path(command[command.index("-x") + 1]).read_bytes() == decoded_signature
        assert Path(command[command.index("-p") + 1]).read_bytes().startswith(b"untrusted comment:")
    monkeypatch.setattr(release_tools.subprocess, "run", verify)
    release_tools.verify_signature(binary, signature, config["plugins"]["updater"]["pubkey"])


def test_generate_checksums(bundles):
    checksums_file = release_tools.generate_checksums(bundles)
    assert checksums_file.is_file()
    content = checksums_file.read_text(encoding="utf-8")
    assert "TFT Studio-setup.exe" in content
    assert "TFT Studio.app.tar.gz" in content
    assert "TFT Studio.AppImage" in content
    # SHA256SUMS itself should not be listed inside SHA256SUMS
    assert "SHA256SUMS" not in content


def test_smoke_sidecar_forwards_options(tmp_path, monkeypatch):
    monkeypatch.setenv("TARGET", "x86_64-pc-windows-msvc" if release_tools.platform.system() == "Windows" else "x86_64-unknown-linux-gnu")
    monkeypatch.setattr(release_tools.platform, "machine", lambda: "x86_64")

    called_cmd = []
    def fake_run(cmd, **kwargs):
        called_cmd.extend(cmd)
        return Mock(returncode=0)

    monkeypatch.setattr(release_tools.subprocess, "run", fake_run)
    release_tools.smoke_sidecar(timeout=45.0, log_dir=tmp_path / "logs")

    assert "--timeout" in called_cmd
    assert "45.0" in called_cmd
    assert "--log-dir" in called_cmd


def test_signing_probe_checks_release_key_without_secret_arguments(monkeypatch):
    config = json.loads(read_manifest("src-tauri/tauri.conf.json"))
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY", "test-private-secret")
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", "")
    monkeypatch.setattr(release_tools, "git", lambda *args: json.dumps(config))
    verifier = Mock()
    monkeypatch.setattr(release_tools, "verify_signature", verifier)

    def sign(command, **kwargs):
        assert "test-private-secret" not in command
        assert kwargs["env"]["TAURI_SIGNING_PRIVATE_KEY_PASSWORD"] == ""
        assert kwargs["capture_output"] is True
        probe = Path(command[-1])
        probe.with_suffix(".txt.sig").write_text("test-signature", encoding="utf-8")

    monkeypatch.setattr(release_tools.subprocess, "run", sign)
    release_tools.signing_probe("a" * 40)
    assert verifier.call_args.args[1:] == ("test-signature", config["plugins"]["updater"]["pubkey"])


@pytest.mark.parametrize("failure", ["decode", "mismatch"])
def test_signing_probe_blocks_bad_secrets_without_exposing_output(monkeypatch, failure):
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY", "private-secret")
    monkeypatch.setattr(release_tools, "git", lambda *args: read_manifest("src-tauri/tauri.conf.json"))

    def sign(command, **kwargs):
        if failure == "decode":
            raise subprocess.CalledProcessError(1, command, stderr="private-secret")
        Path(command[-1]).with_suffix(".txt.sig").write_text("signature", encoding="utf-8")

    monkeypatch.setattr(release_tools.subprocess, "run", sign)
    monkeypatch.setattr(release_tools, "verify_signature", Mock(side_effect=ValueError("private-secret")))
    with pytest.raises(ValueError, match="Signing probe") as error:
        release_tools.signing_probe("a" * 40)
    assert "private-secret" not in str(error.value)
    assert error.value.__suppress_context__
