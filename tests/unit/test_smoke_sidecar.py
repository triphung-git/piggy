"""Unit tests for smoke_sidecar CLI options, diagnostics, and process tree management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts import smoke_sidecar
from tft_studio.core import tempfiles


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


def fake_smoke_session():
    session = MagicMock()
    response = MagicMock(status_code=200, text='<link href="/overlay.css">')
    response.json.return_value = {"ready": True, "success": True}
    session.get.return_value = response
    session.post.return_value = response
    return session


def test_cleanup_failure_has_diagnostics_and_no_pass(tmp_path, monkeypatch, capsys):
    import json

    owner = MagicMock()
    owner.process.poll.return_value = None
    owner.process.wait.return_value = 0
    monkeypatch.setattr(smoke_sidecar, "ProcessTree", MagicMock(return_value=owner))
    monkeypatch.setattr(smoke_sidecar.requests, "Session", fake_smoke_session)
    monkeypatch.setattr(tempfiles, "remove_tree", MagicMock(side_effect=PermissionError("locked profile")))
    log_dir = tmp_path / "logs"
    with pytest.raises(PermissionError, match="locked profile"):
        smoke_sidecar.run_smoke(log_dir=log_dir)
    assert "PASS" not in capsys.readouterr().out
    assert json.loads((log_dir / "diag_metadata.json").read_text())["phase"] == "cleanup"
    assert json.loads((log_dir / "diag_metadata.json").read_text())["error"] == "locked profile"
    assert (log_dir / "process_stderr.log").exists()
    owner.__exit__.assert_called_once()


def test_shutdown_crash_is_not_a_pass(tmp_path, monkeypatch, capsys):
    owner = MagicMock()
    owner.process.poll.return_value = None
    owner.process.wait.return_value = 7
    monkeypatch.setattr(smoke_sidecar, "ProcessTree", MagicMock(return_value=owner))
    monkeypatch.setattr(smoke_sidecar.requests, "Session", fake_smoke_session)
    with pytest.raises(RuntimeError, match="shutdown exited with code 7"):
        smoke_sidecar.run_smoke(log_dir=tmp_path / "logs")
    assert "PASS" not in capsys.readouterr().out
    owner.__exit__.assert_called_once()
