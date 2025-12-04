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
    
    Converts markdown-style formatting to Telegram HTML:
    - **text** -> <b>text</b> (bold)
    - Preserves newlines (\n) - they work naturally in Telegram
    - Escapes HTML entities (<, >, &) that aren't part of HTML tags
    
    Args:
        text: Input text that may contain markdown-style formatting
        
    Returns:
        Text formatted for Telegram HTML parse mode
    """
    if not text:
        return ""
    
    text = str(text)
    
    # First, convert markdown bold **text** to <b>text</b>
    # Use non-greedy matching to handle multiple bold sections
    text = re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', text)
    
    # Escape HTML entities: &, <, > (but preserve existing HTML tags)
    # Strategy: temporarily replace HTML tags, escape, then restore
    html_tags = []
    tag_pattern = r'<[^>]+>'
    
    def replace_tag(match):
        placeholder = f"__HTML_TAG_{len(html_tags)}__"
        html_tags.append(match.group())
        return placeholder
    
    # Replace HTML tags with placeholders
    text_with_placeholders = re.sub(tag_pattern, replace_tag, text)
    
    # Escape entities in the text (excluding placeholders)
    text_with_placeholders = text_with_placeholders.replace('&', '&amp;')
    text_with_placeholders = text_with_placeholders.replace('<', '&lt;')
    text_with_placeholders = text_with_placeholders.replace('>', '&gt;')
    
    # Restore HTML tags
    for i, tag in enumerate(html_tags):
        text_with_placeholders = text_with_placeholders.replace(f"__HTML_TAG_{i}__", tag)
    
    return text_with_placeholders

