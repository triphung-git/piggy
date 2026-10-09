"""
backend/file_watcher.py (Backward compatibility shim)
-----------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.service.file_watcher.
"""

from __future__ import annotations

import sys

import tft_studio.service.file_watcher as _file_watcher

# Biến backend.file_watcher thành alias trực tiếp của tft_studio.service.file_watcher
sys.modules[__name__] = _file_watcher
