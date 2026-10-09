"""
backend/match_service.py (Backward compatibility shim)
------------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.service.match_service.
"""

from __future__ import annotations

import sys

import tft_studio.service.match_service as _match_service

# Biến backend.match_service thành alias trực tiếp của tft_studio.service.match_service
sys.modules[__name__] = _match_service
