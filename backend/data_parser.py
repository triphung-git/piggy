"""
backend/data_parser.py (Backward compatibility shim)
----------------------------------------------------
Module tương thích ngược. Trỏ toàn bộ import sang tft_studio.data.parser.
"""

from __future__ import annotations

import sys

import tft_studio.data.parser as _data_parser

# Biến backend.data_parser thành alias trực tiếp của tft_studio.data.parser
sys.modules[__name__] = _data_parser
