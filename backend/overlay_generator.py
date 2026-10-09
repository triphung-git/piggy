"""
backend/overlay_generator.py (Backward compatibility shim)
----------------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.render.generator.
"""

from __future__ import annotations

import sys

import tft_studio.render.generator as _generator

# Biến backend.overlay_generator thành alias trực tiếp của tft_studio.render.generator
sys.modules[__name__] = _generator
