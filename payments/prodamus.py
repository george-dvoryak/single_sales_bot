# payments/prodamus.py
"""ProDAMUS payment handler."""

import hashlib
import hmac
import requests
from urllib.parse import urlencode, parse_qsl
from config import PRODAMUS_PAYFORM_URL, PRODAMUS_SECRET_KEY, PRODAMUS_TEST_MODE

# Try to import prodamuspy library for proper HMAC verification
try:
    import prodamuspy
    PRODAMUS_LIB_AVAILABLE = True
    print("ProDAMUS: Using prodamuspy library for signature verification")
except ImportError:
    PRODAMUS_LIB_AVAILABLE = False
    print("ProDAMUS: Warning - prodamuspy library not installed, using fallback verification")


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
    Verify ProDAMUS webhook signature using HMAC-SHA256.
    
    ProDAMUS uses HMAC-SHA256, not plain SHA256!
    According to their documentation:
    1. Sort parameters alphabetically by key
    2. Concatenate values with semicolons (;)
    3. Calculate HMAC-SHA256 with secret key
    
    Args:
        data: Webhook data dictionary (parsed form data)
        signature: Signature from 'sign' header
    
    Returns:
        True if signature is valid, False otherwise
    """
    # In test mode, skip signature verification for easier testing
    if PRODAMUS_TEST_MODE:
        print("ProDAMUS: TEST MODE - Skipping signature verification")
        print("ProDAMUS: ⚠️  WARNING: This should only be used for testing!")
        return True
    
    if not PRODAMUS_SECRET_KEY:
        print("ProDAMUS: PRODAMUS_SECRET_KEY is not configured, skipping signature verification")
        return True  # Allow webhooks if secret key is not set (not recommended for production)
    
    if not signature:
        print("ProDAMUS: No signature provided in webhook")
        return False
    
    try:
        print(f"ProDAMUS: Starting signature verification")
        print(f"ProDAMUS: Received signature: {signature}")
        
        # Method 1: Use prodamuspy library (recommended)
        if PRODAMUS_LIB_AVAILABLE:
            print("ProDAMUS: Using prodamuspy library for verification")
            try:
                prodamus = prodamuspy.PyProdamus(PRODAMUS_SECRET_KEY)
                is_valid = prodamus.verify(data, signature)
                
                if is_valid:
                    print(f"ProDAMUS: ✅ Signature verification SUCCESS (prodamuspy)")
                else:
                    print(f"ProDAMUS: ❌ Signature verification FAILED (prodamuspy)")
                
                return is_valid
            except Exception as e:
                print(f"ProDAMUS: Error using prodamuspy library: {e}")
                print(f"ProDAMUS: Falling back to manual HMAC verification")
        
        # Method 2: Manual HMAC-SHA256 verification (fallback)
        print("ProDAMUS: Using manual HMAC-SHA256 verification")
        
        # Filter out the 'sign' parameter if it's in data
        filtered_data = {k: v for k, v in data.items() if k != 'sign'}
        
        print(f"ProDAMUS: Verifying signature for {len(filtered_data)} parameters")
        
        # Sort parameters alphabetically by key
        sorted_keys = sorted(filtered_data.keys())
        print(f"ProDAMUS: Sorted keys: {sorted_keys[:5]}..." if len(sorted_keys) > 5 else f"ProDAMUS: Sorted keys: {sorted_keys}")
        
        # Concatenate values with semicolons
        values_string = ";".join(str(filtered_data[key]) for key in sorted_keys)
        print(f"ProDAMUS: Values string (first 100 chars): {values_string[:100]}...")
        
        # Calculate HMAC-SHA256 (NOT plain SHA256!)
        calculated_signature = hmac.new(
            PRODAMUS_SECRET_KEY.encode('utf-8'),
            values_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        is_valid = hmac.compare_digest(calculated_signature, signature)
        
        print(f"ProDAMUS: Calculated signature: {calculated_signature}")
        print(f"ProDAMUS: Received signature:   {signature}")
        print(f"ProDAMUS: Signatures match: {is_valid}")
        
        if not is_valid:
            print(f"ProDAMUS: ❌ Signature verification FAILED (HMAC)")
        else:
            print(f"ProDAMUS: ✅ Signature verification SUCCESS (HMAC)")
        
        return is_valid
        
    except Exception as e:
        print(f"ProDAMUS: Error verifying signature: {e}")
        import traceback
        traceback.print_exc()
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


