"""Overlay HTML template generation and headless PNG export."""

EXPORT_TIMEOUT = 30
# Includes browser termination and bounded profile cleanup retries.
EXPORT_SHUTDOWN_TIMEOUT = EXPORT_TIMEOUT + 10
