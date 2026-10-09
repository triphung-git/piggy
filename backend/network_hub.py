"""
backend/network_hub.py (Backward compatibility shim)
----------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.api.hub.
"""

from __future__ import annotations

import sys

import tft_studio.api.hub as _hub

# Biến backend.network_hub thành alias trực tiếp của tft_studio.api.hub
sys.modules[__name__] = _hub
