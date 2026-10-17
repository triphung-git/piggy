"""Launch the real sidecar with isolated data and verify HTTP rendering.

Usage: python scripts/smoke_sidecar.py [--binary path/to/tft-backend.exe]
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="tft-smoke-") as folder:
        data = Path(folder)
        (data / "output").mkdir()
        (data / ".env").write_text("RIOT_API_KEY=\nRIOT_ID=\nREGION=VN\n", encoding="utf-8")
        (data / "overlay_config.json").write_text("{}", encoding="utf-8")
        match = json.loads((root / "tests/fixtures/match_1_clean.json").read_text(encoding="utf-8"))
        (data / "output/clean_matches_latest.json").write_text(json.dumps([match]), encoding="utf-8")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        env = {**os.environ, "TFT_APPDATA_DIR": str(data), "TFT_RESOURCE_DIR": str(root),
               "STUDIO_SESSION_TOKEN": "smoke-local-session", "RIOT_API_KEY": "", "RIOT_ID": "",
               "PYTHONPATH": str(root / "src")}
        command = [str(args.binary.resolve())] if args.binary else [sys.executable, "-m", "tft_studio.main_sidecar"]
        log_path = data / "process.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([*command, "--port", str(port)], cwd=root, env=env,
                                       stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            session = requests.Session()
            session.trust_env = False
            session.headers["X-Studio-Token"] = "smoke-local-session"
            base = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(log_path.read_text(encoding="utf-8"))
                    try:
                        if session.get(base + "/api/status", timeout=1).json().get("ready"):
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Sidecar did not become ready")
                result = session.post(base + "/api/render", timeout=15)
                assert result.status_code == 200, result.text
                assert result.json()["success"]
                assert session.get(base + "/api/overlay-html", timeout=5).json()["ready"]
                assert session.get(base + "/assets/background.png", timeout=5).status_code == 200
                assert 'href="/overlay.css"' in session.get(base + "/overlay", timeout=5).text
                print("PASS: real sidecar startup, authenticated render, overlay shell and bundled assets")
            finally:
                try:
                    session.post(base + "/api/shutdown", timeout=2)
                    process.wait(timeout=10)
                except (requests.RequestException, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait(timeout=5)
                session.close()


if __name__ == "__main__":
    main()
