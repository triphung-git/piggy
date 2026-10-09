"""
backend package for TFT Post-Match Studio — Backward compatibility shim.
"""

from __future__ import annotations

from tft_studio.core.config import (
    AppConfig,
    is_configured,
    load_overlay_config,
    save_overlay_config,
)
from tft_studio.data.parser import DDragonLoader, parse_tft_match
from tft_studio.render.exporter import export_html_to_png
from tft_studio.render.generator import generate_overlay_html
from tft_studio.riot.client import RiotTFTClient
from tft_studio.service.match_service import MatchService

__all__ = [
    "AppConfig",
    "DDragonLoader",
    "MatchService",
    "RiotTFTClient",
    "export_html_to_png",
    "generate_overlay_html",
    "is_configured",
    "load_overlay_config",
    "parse_tft_match",
    "save_overlay_config",
]
