"""Unit tests for smoke_sidecar CLI options, diagnostics, and process tree management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import smoke_sidecar


def test_smoke_cli_parser():
    parser = smoke_sidecar.build_parser()
    args = parser.parse_args(["--timeout", "45", "--log-dir", "scratch/logs", "--resource-dir", "pkg/res"])
    assert args.timeout == 45.0
    assert args.log_dir == Path("scratch/logs")
    assert args.resource_dir == Path("pkg/res")


def test_sanitize_log():
    raw = "Failed on token: smoke-local-session and RIOT_API_KEY=RGAPI-12345678-abcd"
    sanitized = smoke_sidecar.sanitize_log(raw, ["smoke-local-session", "RGAPI-12345678-abcd"])
    assert "smoke-local-session" not in sanitized
    assert "RGAPI-12345678-abcd" not in sanitized
    assert "[REDACTED]" in sanitized


def test_kill_process_tree_noop_if_none():
    # Should not raise exception
    smoke_sidecar.kill_process_tree(None)


def test_kill_process_tree_calls_taskkill_on_windows():
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_process.pid = 9999

    with patch("scripts.smoke_sidecar.sys.platform", "win32"), \
         patch("scripts.smoke_sidecar.subprocess.run") as mock_run:
        smoke_sidecar.kill_process_tree(mock_process)
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "taskkill"
        assert "/PID" in cmd
        assert "9999" in cmd


def test_early_exit_diagnostic(tmp_path):
    log_dir = tmp_path / "diag_logs"
    log_dir.mkdir()
    proc_log = tmp_path / "proc.log"
    proc_log.write_text("Fatal: ModuleNotFoundError: fake_module", encoding="utf-8")

    saved = smoke_sidecar.save_diagnostics(
        log_dir=log_dir,
        process_log=proc_log,
        appdata_dir=None,
        exit_code=1,
        secrets=["fake_secret"],
    )
    assert saved is not None
    assert (log_dir / "process_stderr.log").exists()
    assert "fake_module" in (log_dir / "process_stderr.log").read_text(encoding="utf-8")
