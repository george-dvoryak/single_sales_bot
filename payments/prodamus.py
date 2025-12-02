from __future__ import annotations

"""Helpers for working with Prodamus payments (link generation and redirect resolution)."""

from collections.abc import MutableMapping
from typing import Any, Dict

import requests

from config import PRODAMUS_FORM_URL, PRODAMUS_SECRET_KEY
from payments.prodamus_sign_formation import sign, deep_int_to_string


def _http_build_query(dictionary: Dict[str, Any], parent_key: str | bool = False) -> Dict[str, Any]:
    """
    Python equivalent of PHP http_build_query for nested dicts/lists.
    Copied from the Prodamus example file with minimal adaptations.
    """
    items = []
    for key, value in dictionary.items():
        new_key = f"{parent_key}[{key}]" if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(_http_build_query(value, new_key).items())
        elif isinstance(value, (list, tuple)):
            for k, v in enumerate(value):
                items.extend(_http_build_query({str(k): v}, new_key).items())
        else:
            items.append((new_key, value))
    return dict(items)


def build_prodamus_payload(
    course: Dict[str, Any],
    email: str,
    user_id: int,
) -> Dict[str, Any]:
    """
    Build data payload for Prodamus payment link based on course info and buyer email.

    This intentionally stays close to the demo example; you can adjust fields later if needed.
    """
    course_id = str(course.get("id"))
    course_name = course.get("name", "Курс")
    price = str(course.get("price", 0))

    data: Dict[str, Any] = {
        "order_id": f"bot-{user_id}-{course_id}",
        "customer_email": email,
        "products": [
            {
                "sku": course_id,
                "name": course_name,
                "price": price,
                "quantity": "1",
            }
        ],
        # Minimal required fields from the example. All optional/demo-specific fields removed.
        "do": "pay",
    }

    # Sign the payload exactly as in the reference implementation
    if not PRODAMUS_SECRET_KEY:
        raise RuntimeError("PRODAMUS_SECRET_KEY is not configured in .env")

    deep_int_to_string(data)
    data["signature"] = sign(data, PRODAMUS_SECRET_KEY)

    return data


def create_prodamus_payment_link(course: Dict[str, Any], email: str, user_id: int) -> str:
    """
    Create a Prodamus payment URL and resolve it to a short redirect URL.

    Steps:
    - Build payload based on course/email
    - Sign it via Prodamus algorithm
    - Build full payment URL
    - Do a GET with redirects disabled and return Location header if 3xx
    """
    if not PRODAMUS_FORM_URL:
        raise RuntimeError("PRODAMUS_FORM_URL is not configured in .env")

    data = build_prodamus_payload(course, email, user_id)

    # We must call http_build_query AFTER signing, following the original example
    query_params = _http_build_query(data)

    from urllib.parse import urlencode

    link = f"{PRODAMUS_FORM_URL.rstrip('/')}/?{urlencode(query_params)}"

    # Now perform GET and capture redirect URL (3xx Location)
    try:
        resp = requests.get(link, allow_redirects=False, timeout=10)
    except Exception as e:
        raise RuntimeError(f"Error requesting Prodamus URL: {e}") from e

    if 300 <= resp.status_code < 400:
        redirect_url = resp.headers.get("Location")
        if redirect_url:
            return redirect_url

    # Fallback: if no redirect, return original link
    return link


