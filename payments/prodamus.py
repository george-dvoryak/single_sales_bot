# payments/prodamus.py
"""ProDAMUS payment handler."""

import hashlib
import requests
from urllib.parse import urlencode
from config import PRODAMUS_PAYFORM_URL, PRODAMUS_SECRET_KEY


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


def verify_webhook_signature(data: dict, signature: str) -> bool:
    """
    Verify ProDAMUS webhook signature.
    
    According to ProDAMUS documentation:
    1. Sort parameters alphabetically by key
    2. Concatenate values with semicolons (;)
    3. Append secret key
    4. Calculate SHA256 hash
    
    Args:
        data: Webhook data dictionary
        signature: Signature from 'sign' header
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not PRODAMUS_SECRET_KEY:
        print("ProDAMUS: PRODAMUS_SECRET_KEY is not configured, skipping signature verification")
        return True  # Allow webhooks if secret key is not set (not recommended for production)
    
    try:
        # Filter out the 'sign' parameter if it's in data
        filtered_data = {k: v for k, v in data.items() if k != 'sign'}
        
        # Sort parameters alphabetically by key
        sorted_keys = sorted(filtered_data.keys())
        
        # Concatenate values with semicolons
        values_string = ";".join(str(filtered_data[key]) for key in sorted_keys)
        
        # Append secret key
        string_to_hash = values_string + ";" + PRODAMUS_SECRET_KEY
        
        # Calculate SHA256 hash
        calculated_signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
        
        # Compare signatures
        is_valid = calculated_signature == signature
        
        if not is_valid:
            print(f"ProDAMUS: Signature verification failed")
            print(f"ProDAMUS: Expected: {calculated_signature}")
            print(f"ProDAMUS: Received: {signature}")
        
        return is_valid
        
    except Exception as e:
        print(f"ProDAMUS: Error verifying signature: {e}")
        return False


def parse_webhook_data(form_data: dict) -> dict:
    """
    Parse ProDAMUS webhook data.
    
    Args:
        form_data: Raw form data from webhook
    
    Returns:
        Dictionary with parsed webhook data
    """
    return {
        "order_id": form_data.get("order_id", ""),
        "order_num": form_data.get("order_num", ""),
        "payment_status": form_data.get("payment_status", ""),
        "payment_status_description": form_data.get("payment_status_description", ""),
        "sum": form_data.get("sum", "0"),
        "customer_email": form_data.get("customer_email", ""),
        "customer_phone": form_data.get("customer_phone", ""),
        "customer_extra": form_data.get("customer_extra", ""),
        "date": form_data.get("date", ""),
        "payment_type": form_data.get("payment_type", ""),
    }


def is_payment_successful(webhook_data: dict) -> bool:
    """
    Check if payment was successful based on webhook data.
    
    Args:
        webhook_data: Parsed webhook data
    
    Returns:
        True if payment was successful, False otherwise
    """
    return webhook_data.get("payment_status", "").lower() == "success"


