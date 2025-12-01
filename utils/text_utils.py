# utils/text_utils.py
"""Text utility functions for cleaning and formatting."""

import re


def strip_html(text: str) -> str:
    """Remove HTML tags from text (for use in button labels, etc.)"""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', str(text))


def clean_html_text(text: str) -> str:
    """Clean text that might have HTML - remove tags but keep content"""
    if not text:
        return ""
    # Remove HTML tags but keep the text content
    text = re.sub(r'<[^>]+>', '', str(text))
    # Decode common HTML entities if any
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


def rub_to_kopecks(rub: float) -> int:
    """Convert rubles to kopecks for payment API"""
    return int(round(float(rub) * 100))


def rub_str(rub: float) -> str:
    """Format rubles as string with 2 decimal places"""
    return f"{float(rub):.2f}"

