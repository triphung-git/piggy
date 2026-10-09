"""
backend/paths.py
----------------
Backward compatibility shim. Toàn bộ logic đã chuyển sang tft_studio.core.paths.
"""

from tft_studio.core.paths import (
    get_app_dir,
    get_bundle_dir,
    resolve_resource,
)

__all__ = ["get_app_dir", "get_bundle_dir", "resolve_resource"]
