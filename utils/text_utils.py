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


def format_for_telegram_html(text: str) -> str:
    """
    Format text for Telegram HTML parse mode.
    
    Supports HTML formatting directly:
    - HTML tags like <b>, <i>, <u>, <s>, <code>, <pre> are preserved
    - Converts literal \n to actual newlines
    - Escapes HTML entities (<, >, &) that aren't part of valid HTML tags
    
    Args:
        text: Input text that may contain HTML tags and \n for newlines
        
    Returns:
        Text formatted for Telegram HTML parse mode
    """
    if not text:
        return ""
    
    text = str(text)
    
    # Convert literal \n to actual newlines
    text = text.replace('\\n', '\n')
    
    # Escape HTML entities: &, <, > (but preserve existing valid HTML tags)
    # Strategy: temporarily replace valid HTML tags, escape, then restore
    html_tags = []
    # Pattern for valid Telegram HTML tags: <tag>, </tag>, or <tag attr="value">
    # Telegram supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a href="...">
    tag_pattern = r'</?(?:b|i|u|s|code|pre|a(?:\s+[^>]*)?)>'
    
    def replace_tag(match):
        placeholder = f"__HTML_TAG_{len(html_tags)}__"
        html_tags.append(match.group())
        return placeholder
    
    # Replace valid HTML tags with placeholders
    text_with_placeholders = re.sub(tag_pattern, replace_tag, text, flags=re.IGNORECASE)
    
    # Escape entities in the text (excluding placeholders)
    text_with_placeholders = text_with_placeholders.replace('&', '&amp;')
    text_with_placeholders = text_with_placeholders.replace('<', '&lt;')
    text_with_placeholders = text_with_placeholders.replace('>', '&gt;')
    
    # Restore HTML tags
    for i, tag in enumerate(html_tags):
        text_with_placeholders = text_with_placeholders.replace(f"__HTML_TAG_{i}__", tag)
    
    return text_with_placeholders

