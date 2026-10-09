"""
tests/unit/test_file_watcher.py
-------------------------------
Unit tests cho ConfigWatcher (src/tft_studio/service/file_watcher.py).
Kiểm tra khả năng theo dõi mtime, kích hoạt callback tự động và khả năng chống lỗi.
"""

import time
from unittest.mock import MagicMock

from tft_studio.service.file_watcher import ConfigWatcher


def test_config_watcher_init_and_mtimes(tmp_path):
    """Kiểm tra khởi tạo ConfigWatcher và đọc mtimes ban đầu."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("RIOT_API_KEY=test", encoding="utf-8")
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        avatars_dir=avatars_dir,
        poll_interval=0.05,
        debounce_seconds=0.02,
    )

    assert watcher._mtimes["config"] > 0
    assert watcher._mtimes["env"] > 0
    assert watcher._mtimes["avatars"] > 0


def test_config_watcher_nonexistent_paths(tmp_path):
    """Kiểm tra xử lý đường dẫn không tồn tại."""
    cfg_file = tmp_path / "missing_config.json"
    env_file = tmp_path / "missing.env"
    avatars_dir = tmp_path / "missing_avatars"

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        avatars_dir=avatars_dir,
    )

    assert watcher._mtimes["config"] == 0.0
    assert watcher._mtimes["env"] == 0.0
    assert watcher._mtimes["avatars"] == 0.0
    assert watcher._get_file_mtime(cfg_file) == 0.0
    assert watcher._get_dir_max_mtime(avatars_dir) == 0.0
    assert watcher._get_dir_max_mtime(None) == 0.0


def test_config_watcher_get_dir_max_mtime(tmp_path):
    """Kiểm tra _get_dir_max_mtime tìm đúng mtime lớn nhất của file trong thư mục."""
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()

    file1 = avatars_dir / "player1.png"
    file1.write_bytes(b"image1")
    time.sleep(0.02)
    file2 = avatars_dir / "player2.png"
    file2.write_bytes(b"image2")

    watcher = ConfigWatcher(
        config_path=tmp_path / "c.json",
        env_path=tmp_path / "e.env",
        avatars_dir=avatars_dir,
    )

    max_mtime = watcher._get_dir_max_mtime(avatars_dir)
    assert max_mtime == file2.stat().st_mtime


def test_config_watcher_detects_config_change(tmp_path):
    """Kiểm tra thay đổi file config kích hoạt on_config_changed."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        poll_interval=0.05,
        debounce_seconds=0.02,
    )

    callback = MagicMock()
    watcher.on_config_changed = callback

    watcher.start()
    try:
        time.sleep(0.08)
        # Sửa file config
        cfg_file.write_text('{"tournament_title": "NEW"}', encoding="utf-8")
        time.sleep(0.2)
        assert callback.called
    finally:
        watcher.stop()


def test_config_watcher_detects_env_change(tmp_path):
    """Kiểm tra thay đổi file .env kích hoạt on_env_changed."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("OLD=1", encoding="utf-8")

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        poll_interval=0.05,
        debounce_seconds=0.02,
    )

    callback = MagicMock()
    watcher.on_env_changed = callback

    watcher.start()
    try:
        time.sleep(0.08)
        # Sửa file .env
        env_file.write_text("NEW=2", encoding="utf-8")
        time.sleep(0.2)
        assert callback.called
    finally:
        watcher.stop()


def test_config_watcher_detects_avatar_change(tmp_path):
    """Kiểm tra thêm ảnh vào thư mục avatars kích hoạt on_avatars_changed."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        avatars_dir=avatars_dir,
        poll_interval=0.05,
        debounce_seconds=0.02,
    )

    callback = MagicMock()
    watcher.on_avatars_changed = callback

    watcher.start()
    try:
        time.sleep(0.08)
        # Thêm file ảnh mới
        new_avatar = avatars_dir / "new_avatar.png"
        new_avatar.write_bytes(b"avatar_data")
        time.sleep(0.2)
        assert callback.called
    finally:
        watcher.stop()


def test_config_watcher_callback_exception_tolerance(tmp_path):
    """Kiểm tra nếu callback ném ngoại lệ, watcher loop vẫn chạy mà không bị crash."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        avatars_dir=avatars_dir,
        poll_interval=0.05,
        debounce_seconds=0.01,
    )

    def failing_callback():
        raise RuntimeError("Test crash in callback")

    watcher.on_config_changed = failing_callback
    watcher.on_env_changed = failing_callback
    watcher.on_avatars_changed = failing_callback

    watcher.start()
    try:
        time.sleep(0.08)
        cfg_file.write_text('{"a": 1}', encoding="utf-8")
        env_file.write_text("A=1", encoding="utf-8")
        (avatars_dir / "a.png").write_bytes(b"test")
        time.sleep(0.2)
        # Luồng vẫn sống
        assert watcher._thread.is_alive()
    finally:
        watcher.stop()


def test_config_watcher_start_stop_idempotency(tmp_path):
    """Kiểm tra start/stop nhiều lần liên tiếp an toàn."""
    cfg_file = tmp_path / "overlay_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    watcher = ConfigWatcher(
        config_path=cfg_file,
        env_path=env_file,
        poll_interval=0.1,
    )

    watcher.start()
    thread1 = watcher._thread
    watcher.start()  # Gọi lần 2 không được tạo luồng mới
    assert watcher._thread is thread1

    watcher.stop()
    assert not watcher._thread.is_alive()
    watcher.stop()  # Gọi stop lần 2 không lỗi
