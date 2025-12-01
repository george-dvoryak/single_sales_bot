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
    print("=" * 80)
    print("🔗 ProDAMUS: Generating payment link")
    print("=" * 80)
    print(f"📋 Order ID: {order_id}")
    print(f"📧 Customer Email: {customer_email}")
    print(f"📱 Customer Phone: {customer_phone if customer_phone else '(not provided)'}")
    print(f"📦 Product Name: {product_name}")
    print(f"💰 Price: {price} RUB")
    print(f"📝 Customer Extra: {customer_extra if customer_extra else '(not provided)'}")
    
    if not PRODAMUS_PAYFORM_URL:
        print("❌ ERROR: PRODAMUS_PAYFORM_URL is not configured")
        print("=" * 80)
        return None
    
    print(f"\n🌐 ProDAMUS Payform URL: {PRODAMUS_PAYFORM_URL}")
    
    # Build payment parameters
    print(f"\n📋 Step 1: Building payment parameters")
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
        print(f"   ✅ Added customer_phone: {customer_phone}")
    if customer_extra:
        params["customer_extra"] = customer_extra
        print(f"   ✅ Added customer_extra: {customer_extra}")
    
    print(f"   Total parameters: {len(params)}")
    print(f"   Parameters: {params}")
    
    # Build full URL with parameters
    long_url = f"{PRODAMUS_PAYFORM_URL}?{urlencode(params)}"
    print(f"\n📋 Step 2: Built long URL")
    print(f"   URL length: {len(long_url)} chars")
    print(f"   URL preview: {long_url[:200]}...")
    
    try:
        print(f"\n📋 Step 3: Making request to get shortened URL")
        print(f"   Following redirects: True")
        print(f"   Timeout: 10 seconds")
        
        # Make a request to get the shortened URL (follow redirects)
        response = requests.get(long_url, allow_redirects=True, timeout=10)
        
        print(f"   Response status: {response.status_code}")
        print(f"   Final URL: {response.url}")
        print(f"   URL length: {len(response.url)} chars")
        
        # The final URL after redirects is the shortened payment link
        short_url = response.url
        
        print(f"\n✅ Payment link generated successfully!")
        print(f"   Short URL: {short_url}")
        print("=" * 80)
        
        return short_url
        
    except requests.exceptions.Timeout as e:
        print(f"\n❌ ERROR: Request timeout")
        print(f"   Error: {e}")
        print("=" * 80)
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: Request failed")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error: {e}")
        print("=" * 80)
        return None
    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return None


# All verification is now handled by prodamuspy library in main.py
# No custom verification functions needed


