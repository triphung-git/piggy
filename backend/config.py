"""
backend/config.py
-----------------
Backward compatibility shim. Toàn bộ logic đã chuyển sang tft_studio.core.config.
"""

import sys

import tft_studio.core.config as _core_config

# Biến backend.config thành alias trực tiếp của tft_studio.core.config
# Giúp mọi import và mock/patch trên backend.config trỏ thẳng vào tft_studio.core.config
sys.modules[__name__] = _core_config
