"""Atomic publication of files read concurrently by OBS and background workers."""

import os
import threading
import uuid
from pathlib import Path

CONFIG_LOCK = threading.RLock()
RENDER_LOCK = threading.RLock()
EXPORT_LOCK = threading.RLock()


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".tft-{uuid.uuid4().hex[:12]}.tmp")
    try:
        if isinstance(data, str):
            temporary.write_text(data, encoding="utf-8")
        else:
            temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
