"""Utility for loading and caching text messages from Google Sheets."""

from typing import Dict
from google_sheets import get_texts_data
from utils.logger import log_warning

# Cache for texts
_texts_cache: Dict[str, str] = {}


def get_texts() -> Dict[str, str]:
    """Get texts from Google Sheets, with caching."""
    global _texts_cache
    if not _texts_cache:
        try:
            _texts_cache = get_texts_data()
        except Exception as e:
            log_warning("text_loader", f"Could not fetch texts from Google Sheets: {e}")
            _texts_cache = {}
    return _texts_cache


def get_text(key: str, default: str = "") -> str:
    """Get a text value by key, with fallback to default."""
    texts = get_texts()
    return texts.get(key, default)


def clear_cache() -> None:
    """Clear the texts cache (useful for testing or reloading)."""
    global _texts_cache
    _texts_cache = {}

