# payments/prodamus.py
"""Prodamus payment link generation and processing."""

import time
import urllib.parse
import requests
from typing import Optional
from config import PRODAMUS_BASE_URL


def generate_order_num(user_id: int, course_id: str) -> str:
    """
    Generate order_num for Prodamus payment.
    Format: user_id_course_id_timestamp (only digits and underscores),
    used in webhook to identify user and course.
    """
    timestamp = int(time.time())
    return f"{user_id}_{course_id}_{timestamp}"


def build_payment_link(
    order_id: str,
    order_num: str,
    customer_email: str,
    customer_phone: str,
    course_name: str,
    price: float,
    customer_extra: str = ""
) -> str:
    """
    Build Prodamus payment link with all required parameters.
    
    Example:
    https://demo.payform.ru/?order_id=test&customer_phone=79998887755&products[0][price]=2000&products[0][quantity]=1&products[0][name]=Обучающие материалы&customer_extra=Полная оплата курса&do=pay
    """
    base_url = PRODAMUS_BASE_URL.rstrip('/')
    
    params = {
        # Prodamus will echo order_num back in webhook, we use it as main identifier
        'order_id': order_id,
        'order_num': order_num,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'products[0][price]': str(price),
        'products[0][quantity]': '1',
        'products[0][name]': course_name,
        'do': 'pay'
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
        response = requests.get(payment_link, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return response.url
        else:
            print(f"[prodamus] Error getting payment URL: status {response.status_code}")
            return None
    except Exception as e:
        print(f"[prodamus] Exception getting payment URL: {e}")
        return None

