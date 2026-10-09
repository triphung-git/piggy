"""
backend/riot_client.py
----------------------
Backward compatibility shim. Toàn bộ logic đã chuyển sang tft_studio.riot.client.
"""

import sys

import tft_studio.riot.client as _riot_client

# Biến backend.riot_client thành alias trực tiếp của tft_studio.riot.client
sys.modules[__name__] = _riot_client
