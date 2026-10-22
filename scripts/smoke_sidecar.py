"""Launch the real sidecar with isolated data and verify HTTP rendering.

Usage: python scripts/smoke_sidecar.py [--binary path/to/tft-backend.exe] [--timeout 30] [--log-dir path] [--resource-dir path]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test TFT Studio sidecar")
    parser.add_argument("--binary", type=Path, default=None, help="Path to compiled sidecar binary")
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds (default: 30)")
    parser.add_argument("--log-dir", type=Path, default=None, help="Durable directory to write diagnostic logs")
    parser.add_argument("--resource-dir", type=Path, default=None, help="Explicit resource directory")
    return parser


def sanitize_log(content: str, secrets: list[str]) -> str:
    """Sanitize secrets such as tokens, API keys and Riot IDs from log strings."""
    sanitized = content
    for secret in secrets:
        if secret and len(secret) >= 4:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def kill_process_tree(process: subprocess.Popen | None) -> None:
    """Kill process and all child processes created by PyInstaller bootloader."""
    if process is None or process.poll() is not None:
        return

    pid = process.pid
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    else:
        with contextlib.suppress(Exception):
            process.kill()

    with contextlib.suppress(Exception):
        process.wait(timeout=5)



def save_diagnostics(
    log_dir: Path | None,
    process_log: Path | None,
    appdata_dir: Path | None,
    exit_code: int | None,
    secrets: list[str],
) -> Path | None:
    """Save durable sanitized logs for post-mortem analysis and CI artifacts."""
    if not log_dir:
        return None
    try:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        if process_log and process_log.is_file():
            raw = process_log.read_text(encoding="utf-8", errors="replace")
            (log_dir / "process_stderr.log").write_text(sanitize_log(raw, secrets), encoding="utf-8")

        if appdata_dir:
            studio_log = Path(appdata_dir) / "logs" / "studio.log"
            if studio_log.is_file():
                raw = studio_log.read_text(encoding="utf-8", errors="replace")
                (log_dir / "studio.log").write_text(sanitize_log(raw, secrets), encoding="utf-8")

        metadata = {
            "exit_code": exit_code,
            "timestamp": time.time(),
            "platform": sys.platform,
        }
        (log_dir / "diag_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return log_dir
    except Exception as exc:
        sys.stderr.write(f"[WARN] Failed to write diagnostics to {log_dir}: {exc}\n")
        return None


def run_smoke(
    binary: Path | None = None,
    timeout: float = 30.0,
    log_dir: Path | None = None,
    resource_dir: Path | None = None,
) -> dict[str, float]:
    """Execute real sidecar smoke test, returning metrics on elapsed durations."""
    res_root = Path(resource_dir).resolve() if resource_dir else ROOT
    token = "smoke-local-session"
    secrets_to_redact = [token]

    with tempfile.TemporaryDirectory(prefix="tft-smoke-") as folder:
        data = Path(folder)
        (data / "output").mkdir()
        (data / ".env").write_text("RIOT_API_KEY=\nRIOT_ID=\nREGION=VN\n", encoding="utf-8")
        (data / "overlay_config.json").write_text("{}", encoding="utf-8")

        fixture_match = res_root / "tests" / "fixtures" / "match_1_clean.json"
        if not fixture_match.exists():
            fixture_match = ROOT / "tests" / "fixtures" / "match_1_clean.json"
        match = json.loads(fixture_match.read_text(encoding="utf-8"))
        (data / "output" / "clean_matches_latest.json").write_text(json.dumps([match]), encoding="utf-8")

        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        env = {
            **os.environ,
            "TFT_APPDATA_DIR": str(data),
            "TFT_RESOURCE_DIR": str(res_root),
            "STUDIO_SESSION_TOKEN": token,
            "RIOT_API_KEY": "",
            "RIOT_ID": "",
            "PYTHONPATH": str(ROOT / "src"),
        }
        if resource_dir:
            env["TFT_ISOLATED_RESOURCES"] = "1"

        command = [str(binary.resolve())] if binary else [sys.executable, "-m", "tft_studio.main_sidecar"]
        log_path = data / "process.log"
        log_file = log_path.open("w", encoding="utf-8")

        process = None
        session = requests.Session()
        session.trust_env = False
        session.headers["X-Studio-Token"] = token
        base = f"http://127.0.0.1:{port}"

        t_start = time.monotonic()
        t_startup = 0.0
        t_render = 0.0
        t_shutdown = 0.0

        try:
            process = subprocess.Popen(
                [*command, "--port", str(port)],
                cwd=str(res_root),
                env=env,
                stdout=log_file,
                stderr=log_file,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # Close python write handle so child holds it exclusively
            log_file.close()

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                exit_code = process.poll()
                if exit_code is not None:
                    save_diagnostics(log_dir, log_path, data, exit_code, secrets_to_redact)
                    err_msg = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
                    raise RuntimeError(f"Sidecar exited prematurely with code {exit_code}:\n{err_msg}")
                try:
                    res = session.get(base + "/api/status", timeout=1)
                    if res.status_code == 200 and res.json().get("ready"):
                        t_startup = time.monotonic() - t_start
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.1)
            else:
                save_diagnostics(log_dir, log_path, data, process.poll(), secrets_to_redact)
                raise TimeoutError(f"Sidecar did not become ready within {timeout}s on port {port}")

            # Verify authenticated render
            t_render_start = time.monotonic()
            render_res = session.post(base + "/api/render", timeout=15)
            assert render_res.status_code == 200, f"Render failed ({render_res.status_code}): {render_res.text}"
            assert render_res.json().get("success"), f"Render JSON missing success: {render_res.text}"
            t_render = time.monotonic() - t_render_start

            # Verify overlay HTML and static assets
            html_res = session.get(base + "/api/overlay-html", timeout=5)
            assert html_res.status_code == 200 and html_res.json().get("ready"), "Overlay HTML endpoint not ready"

            bg_res = session.get(base + "/assets/background.png", timeout=5)
            assert bg_res.status_code == 200, f"Background asset failed with status {bg_res.status_code}"

            overlay_res = session.get(base + "/overlay", timeout=5)
            assert overlay_res.status_code == 200 and 'href="/overlay.css"' in overlay_res.text, "Overlay shell missing stylesheet"

            print(
                f"PASS: real sidecar startup ({t_startup:.2f}s), "
                f"render ({t_render:.2f}s), overlay shell and bundled assets"
            )

        except Exception:
            if process and process.poll() is None:
                kill_process_tree(process)
            save_diagnostics(log_dir, log_path, data, process.poll() if process else None, secrets_to_redact)
            raise
        finally:
            t_shut_start = time.monotonic()
            try:
                session.post(base + "/api/shutdown", timeout=2)
                if process:
                    process.wait(timeout=10)
            except (requests.RequestException, subprocess.TimeoutExpired):
                if process:
                    kill_process_tree(process)
            t_shutdown = time.monotonic() - t_shut_start
            session.close()

            # Ensure log file is definitely closed before exiting temp directory
            if not log_file.closed:
                log_file.close()

        return {"startup": t_startup, "render": t_render, "shutdown": t_shutdown}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        run_smoke(
            binary=args.binary,
            timeout=args.timeout,
            log_dir=args.log_dir,
            resource_dir=args.resource_dir,
        )
    except Exception as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
