"""Exercise the real locked Tauri signer and Minisign with disposable test keys."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import release_tools

CLI = release_tools.ROOT / "node_modules" / "@tauri-apps" / "cli" / "tauri.js"
pytestmark = pytest.mark.skipif(
    not CLI.is_file() or not shutil.which("node") or not shutil.which("minisign"),
    reason="Requires npm ci, Node and Minisign (installed by CI)",
)


@pytest.fixture(scope="module")
def signing_keys(tmp_path_factory):
    directory = tmp_path_factory.mktemp("signing-keys")
    keys = {}
    for name, password in (("encrypted", "qa-only-test-password"), ("empty", "")):
        path = directory / f"{name}.key"
        subprocess.run(["node", str(CLI), "signer", "generate", "--ci", "-w", str(path), "-p", password],
                       check=True, capture_output=True, timeout=60)
        keys[name] = (path.read_text(encoding="utf-8").strip(),
                      Path(f"{path}.pub").read_text(encoding="utf-8").strip(), password)
    return keys


@pytest.mark.parametrize("case", ["encrypted", "empty", "wrong-password", "truncated", "mismatch"])
def test_real_signing_preflight(case, signing_keys, monkeypatch):
    private, public, password = signing_keys["empty" if case == "empty" else "encrypted"]
    if case == "wrong-password":
        password = "incorrect-test-password"
    elif case == "truncated":
        private = private[:len(private) // 2]
    elif case == "mismatch":
        public = signing_keys["empty"][1]
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY", private)
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", password)
    monkeypatch.setattr(release_tools, "git", lambda *args: json.dumps({"plugins": {"updater": {"pubkey": public}}}))
    if case in ("encrypted", "empty"):
        release_tools.signing_probe("test-release-ref")
    else:
        with pytest.raises(ValueError, match="Signing probe"):
            release_tools.signing_probe("test-release-ref")
