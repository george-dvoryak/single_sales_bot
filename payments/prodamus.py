# payments/prodamus.py
"""Prodamus payment link generation and processing."""

import time
import urllib.parse
import requests
from typing import Optional
from config import PRODAMUS_BASE_URL, PRODAMUS_SYS
from utils.logger import log_error, log_warning


def generate_order_id(user_id: int, course_id: str) -> str:
    """
    Generate order_id for Prodamus payment.
    Format: user_id_course_id_timestamp (only digits and underscores),
    used to identify user and course.
    """
    timestamp = int(time.time())
    return f"{user_id}_{course_id}_{timestamp}"


def build_payment_link(
    order_id: str,
    course_name: str,
    price: float,
    customer_extra: str = ""
) -> str:
    """
    Build Prodamus payment link with all required parameters.
    """
    base_url = PRODAMUS_BASE_URL.rstrip('/')
    
    params = {
        'order_id': order_id,
        'products[0][price]': str(price),
        'products[0][quantity]': '1',
        'products[0][name]': course_name,
        'do': 'link',
        'sys': PRODAMUS_SYS,
    }
    
    if customer_extra:
        params['customer_extra'] = customer_extra
    
    # Build query string
    query_string = urllib.parse.urlencode(params)
    payment_link = f"{base_url}/?{query_string}"
    
    return payment_link


def get_payment_url(payment_link: str) -> Optional[str]:
    """
    Make GET request to payment link and extract the short payment URL from response.
    First tries to extract URL from response body (JSON or text), then falls back to redirect URL.
    Returns the short payment URL (e.g., https://demo.payform.ru/p/p5z2micwqc9c26/)
    """
    try:
        from utils.logger import log_info
        import json
        import re
        
        log_info_prefix = f"get_payment_url: link={payment_link[:200]}"
        log_info("prodamus", f"{log_info_prefix} -> making GET request")
        
        # Make GET request without following redirects first to check response body
        response = requests.get(payment_link, allow_redirects=False, timeout=10)

        if response.status_code == 200:
            # Try to extract URL from JSON response
            try:
                json_data = response.json()
                # Check common JSON fields for URL
                for key in ['url', 'link', 'payment_url', 'short_url', 'redirect_url']:
                    if key in json_data and isinstance(json_data[key], str):
                        url = json_data[key].strip()
                        if url.startswith('http'):
                            log_info("prodamus", f"{log_info_prefix} -> found URL in JSON field '{key}': {url[:100]}")
                            return url
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Try to extract URL from text response (look for URLs in the response)
            try:
                text = response.text
                # Look for URLs in the response text
                url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+'
                urls = re.findall(url_pattern, text)
                if urls:
                    # Prefer URLs that look like payment URLs (contain /p/ or similar)
                    for url in urls:
                        if '/p/' in url or 'payform' in url.lower() or 'prodamus' in url.lower():
                            log_info("prodamus", f"{log_info_prefix} -> found URL in text response: {url[:100]}")
                            return url
                    # If no payment-like URL found, return first URL
                    log_info("prodamus", f"{log_info_prefix} -> found URL in text response: {urls[0][:100]}")
                    return urls[0]
            except Exception:
                pass
        
        # If status is redirect (3xx), follow it
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get('Location')
            if redirect_url:
                log_info("prodamus", f"{log_info_prefix} -> following redirect to: {redirect_url[:100]}")
                # Follow redirects to get final URL
                final_response = requests.get(redirect_url, allow_redirects=True, timeout=10)
                if final_response.status_code == 200:
                    return final_response.url
        
        # If we got here, try with redirects enabled as fallback
        log_info("prodamus", f"{log_info_prefix} -> trying with redirects enabled")
        response_with_redirects = requests.get(payment_link, allow_redirects=True, timeout=10)
        if response_with_redirects.status_code == 200:
            final_url = response_with_redirects.url
            log_info("prodamus", f"{log_info_prefix} -> got final URL from redirect: {final_url[:100]}")
            return final_url

        # Non-200 status – log detailed information for diagnostics
        body_snippet = ""
        try:
            body_snippet = response.text[:500]
        except Exception:
            body_snippet = "<unable to read body>"

        log_warning(
            "prodamus",
            f"{log_info_prefix} -> non-200 response: "
            f"status={response.status_code}, "
            f"headers={dict(response.headers)}, "
            f"body_snippet={body_snippet!r}",
        )
        return None
    except Exception as e:
        # Network / parsing error – log full stack trace
        log_error("prodamus", f"Exception getting payment URL for link={payment_link[:200]}: {e}", exc_info=True)
        return None

