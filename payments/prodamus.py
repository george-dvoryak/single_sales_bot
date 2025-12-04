# payments/prodamus.py
"""Prodamus payment link generation and processing."""

import time
import urllib.parse
import requests
from typing import Optional
from config import PRODAMUS_BASE_URL
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
    }
    
    if customer_extra:
        params['customer_extra'] = customer_extra
    
    # Build query string
    query_string = urllib.parse.urlencode(params)
    payment_link = f"{base_url}/?{query_string}"
    
    return payment_link


def get_payment_url(payment_link: str) -> Optional[str]:
    """
    Make GET request to payment link and extract the actual payment URL from redirect.
    Returns the final payment URL (e.g., https://demo.payform.ru/p/p5z2micwqc9c26/)
    """
    try:
        # Follow redirects and get final URL
        from utils.logger import log_info
        log_info_prefix = f"get_payment_url: link={payment_link[:200]}"
        response = requests.get(payment_link, allow_redirects=True, timeout=10)

        if response.status_code == 200:
            final_url = response.url
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

