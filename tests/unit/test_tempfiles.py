"""Cleanup retries must be bounded and preserve the primary failure."""

from unittest.mock import Mock

import pytest

from tft_studio.core import tempfiles


def test_transient_lock_is_retried(monkeypatch, tmp_path):
    remove = Mock(side_effect=[PermissionError("locked"), None])
    sleep = Mock()
    monkeypatch.setattr(tempfiles.shutil, "rmtree", remove)
    monkeypatch.setattr(tempfiles.time, "sleep", sleep)
    tempfiles.remove_tree(tmp_path)
    assert remove.call_count == 2
    sleep.assert_called_once_with(0.1)


def test_permanent_lock_fails_after_bounded_retries(monkeypatch, tmp_path):
    remove = Mock(side_effect=PermissionError("locked"))
    monkeypatch.setattr(tempfiles.shutil, "rmtree", remove)
    monkeypatch.setattr(tempfiles.time, "sleep", Mock())
    with pytest.raises(PermissionError):
        tempfiles.remove_tree(tmp_path)
    assert remove.call_count == 6


def test_cleanup_does_not_mask_primary_error(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfiles, "remove_tree", Mock(side_effect=PermissionError("cleanup")))
    with pytest.raises(ValueError, match="primary"), tempfiles.temporary_directory(prefix="test-", dir=tmp_path):
        raise ValueError("primary")
