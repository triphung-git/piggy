"""Shutdown must wait for export completion and report a stuck worker."""

import threading
from unittest.mock import Mock

import pytest

from tft_studio.render import EXPORT_SHUTDOWN_TIMEOUT
from tft_studio.service.controller import StudioController


@pytest.mark.parametrize("stuck", [False, True])
def test_close_waits_for_export_worker(stuck):
    controller = StudioController.__new__(StudioController)
    controller._closed = False
    controller._export_requested = threading.Event()
    controller._config_watcher = Mock()
    controller._match_service = Mock()
    controller._export_worker = Mock()
    controller._export_worker.is_alive.return_value = stuck
    if stuck:
        with pytest.raises(RuntimeError, match="exporter did not stop"):
            controller.close()
    else:
        controller.close()
    assert controller._closed
    assert controller._export_requested.is_set()
    controller._export_worker.join.assert_called_once_with(timeout=EXPORT_SHUTDOWN_TIMEOUT)
