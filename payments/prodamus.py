# payments/prodamus.py
"""ProDAMUS payment handler."""

import requests
from urllib.parse import urlencode
from config import PRODAMUS_PAYFORM_URL


def generate_payment_link(order_id: str, customer_email: str, customer_phone: str, 
                          product_name: str, price: float, customer_extra: str = "") -> str:
    """
    Generate ProDAMUS payment link and return shortened URL.
    
    Args:
        order_id: Unique order identifier (e.g., "user_id:course_id")
        customer_email: Customer email (required)
        customer_phone: Customer phone (optional, e.g., "79998887755")
        product_name: Name of the product/course
        price: Price in rubles
        customer_extra: Additional information about the order
    
    Returns:
        Shortened payment URL or None on error
    """
    if not PRODAMUS_PAYFORM_URL:
        print("ProDAMUS: PRODAMUS_PAYFORM_URL is not configured")
        return None
    
    # Build payment parameters
    params = {
        "order_id": order_id,
        "customer_email": customer_email,
        "products[0][price]": int(price),  # ProDAMUS uses integer rubles
        "products[0][quantity]": 1,
        "products[0][name]": product_name,
        "do": "pay"
    }
    
    # Add optional parameters
    if customer_phone:
        params["customer_phone"] = customer_phone
    if customer_extra:
        params["customer_extra"] = customer_extra
    
    # Build full URL with parameters
    long_url = f"{PRODAMUS_PAYFORM_URL}?{urlencode(params)}"
    
    try:
        # Make a request to get the shortened URL (follow redirects)
        response = requests.get(long_url, allow_redirects=True, timeout=10)
        
        # The final URL after redirects is the shortened payment link
        short_url = response.url
        
        print(f"ProDAMUS: Generated payment link for order {order_id}")
        return short_url
        
    except Exception as e:
        print(f"ProDAMUS: Error generating payment link: {e}")
        return None


# All verification is now handled by prodamuspy library in main.py
# No custom verification functions needed


