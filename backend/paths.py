"""
backend/paths.py
----------------
Backward compatibility shim. Toàn bộ logic đã chuyển sang tft_studio.core.paths.
"""

import sys
import tft_studio.core.paths as _core_paths

# Biến backend.paths thành alias trực tiếp của tft_studio.core.paths
sys.modules[__name__] = _core_paths
