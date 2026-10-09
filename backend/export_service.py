"""
backend/export_service.py (Backward compatibility shim)
-------------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.render.exporter.
"""

from __future__ import annotations

import sys

import tft_studio.render.exporter as _exporter

# Biến backend.export_service thành alias trực tiếp của tft_studio.render.exporter
sys.modules[__name__] = _exporter
