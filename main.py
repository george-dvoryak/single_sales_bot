# main.py
"""
Simple Sales Bot - Clean and Modular Version
Main entry point for the bot (polling or webhook mode)
"""

import time
import telebot
from flask import Flask, request, abort

from config import (
    TELEGRAM_BOT_TOKEN, 
    USE_WEBHOOK, 
    WEBHOOK_URL, 
    WEBHOOK_PATH,
    WEBHOOK_SECRET_TOKEN,
    ADMIN_IDS,
    ENABLE_PRODAMUS,
    PRODAMUS_SECRET_KEY
)

# Import handlers
from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
from utils.channel import check_course_channels
from google_sheets import get_courses_data


# Initialize bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)

# Register all handlers
# IMPORTANT: payment_handlers must be registered FIRST to give priority to email collection
payment_handlers.register_handlers(bot)
basic_handlers.register_handlers(bot)
catalog_handlers.register_handlers(bot)
admin_handlers.register_handlers(bot)

# Flask app for webhook mode (WSGI server on PythonAnywhere)
application = Flask(__name__)


@application.get("/")
def _health():
    """Health check endpoint"""
    return "OK", 200


@application.get("/diag")
def _diag():
    """Lightweight diagnostics endpoint"""
    try:
        report = check_course_channels(bot, get_courses_data)
    except Exception as e:
        report = f"diag error: {e}"
    return report, 200


# Webhook endpoint - use WEBHOOK_PATH if set, otherwise use default path
webhook_route = WEBHOOK_PATH if WEBHOOK_PATH else f"/{TELEGRAM_BOT_TOKEN}"


@application.post(webhook_route)
def _webhook():
    """Telegram webhook endpoint"""
    # Validate Telegram secret header if configured
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
        abort(403)
    # Forward the update to pyTelegramBotAPI
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Error processing webhook update: {e}")
    return "OK", 200


@application.post("/prodamus_webhook")
def _prodamus_webhook():
    """ProDAMUS payment webhook endpoint"""
    if not ENABLE_PRODAMUS:
        abort(404)
    
    try:
        from payments.hmac_verifier import HmacPy
        from handlers.payment_handlers import handle_prodamus_payment
        
        print("=" * 80)
        print("✅ Using HmacPy (exact PHP match implementation)")
        print("=" * 80)
        
        print("=" * 80)
        print("🔔 ProDAMUS WEBHOOK RECEIVED")
        print("=" * 80)
        print(f"⏰ Time: {request.environ.get('REQUEST_TIME', 'unknown')}")
        print(f"🌐 Remote IP: {request.remote_addr}")
        print(f"🌐 X-Forwarded-For: {request.headers.get('X-Forwarded-For', 'not set')}")
        print(f"🌐 X-Real-IP: {request.headers.get('X-Real-IP', 'not set')}")
        print(f"📋 Method: {request.method}")
        print(f"📝 Content-Type: {request.content_type}")
        print(f"📏 Content-Length: {request.content_length}")
        
        # Check for proxy/gateway indicators
        print(f"\n🔍 PROXY/GATEWAY CHECK:")
        proxy_headers = ['X-Forwarded-For', 'X-Forwarded-Proto', 'X-Real-IP', 
                        'Via', 'X-Forwarded-Host', 'Forwarded', 'CF-Ray']
        found_proxy = False
        for ph in proxy_headers:
            value = request.headers.get(ph)
            if value:
                print(f"  ⚠️  {ph}: {value}")
                found_proxy = True
        if not found_proxy:
            print(f"  ✅ No proxy headers detected")
        
        # Check WSGI environment for modifications
        print(f"\n🔍 WSGI ENVIRONMENT:")
        print(f"  SERVER_SOFTWARE: {request.environ.get('SERVER_SOFTWARE', 'unknown')}")
        print(f"  wsgi.input type: {type(request.environ.get('wsgi.input'))}")
        print(f"  CONTENT_LENGTH: {request.environ.get('CONTENT_LENGTH', 'not set')}")
        
        # Log all headers
        print("\n📨 HEADERS:")
        for header, value in request.headers:
            if header.lower() == 'sign':
                print(f"  {header}: {value[:30]}... (truncated)")
            else:
                print(f"  {header}: {value}")
        
        print("\n" + "=" * 80)
        print("STEP 0: Initialize HmacPy verifier")
        print("=" * 80)
        print(f"🔑 Secret key length: {len(PRODAMUS_SECRET_KEY)} chars")
        print(f"🔑 Secret key (first 10 chars): {PRODAMUS_SECRET_KEY[:10]}...")
        print("✅ HmacPy ready (exact PHP match)")
        
        print("\n" + "=" * 80)
        print("STEP 1: Get raw body from webhook")
        print("=" * 80)
        
        # Get raw body BEFORE Flask processes it
        raw_body = request.get_data(as_text=True)
        print(f"📦 Raw body length: {len(raw_body)} bytes")
        print(f"📦 Raw body type: {type(raw_body)}")
        print(f"📦 Raw body (first 300 chars):\n{raw_body[:300]}...")
        if len(raw_body) > 300:
            print(f"📦 Raw body (last 100 chars):\n...{raw_body[-100:]}")
        
        # Also check what Flask's request.form parsed
        print(f"\n🔍 COMPARISON: Flask request.form vs raw body")
        flask_parsed = request.form.to_dict()
        print(f"📦 Flask request.form keys: {list(flask_parsed.keys())}")
        print(f"📦 Flask request.form sample: {dict(list(flask_parsed.items())[:3])}")
        
        # Check if body was consumed/modified
        print(f"\n🔍 BODY INTEGRITY CHECK:")
        print(f"📦 request.content_length: {request.content_length}")
        print(f"📦 len(raw_body): {len(raw_body)}")
        print(f"📦 Match: {request.content_length == len(raw_body) if request.content_length else 'N/A'}")
        
        # Calculate hash of raw body for verification
        import hashlib
        raw_body_hash = hashlib.md5(raw_body.encode('utf-8')).hexdigest()
        print(f"📦 Raw body MD5 hash: {raw_body_hash}")
        
        # Check if there are any encoding issues
        print(f"\n🔍 ENCODING CHECK:")
        print(f"📦 Raw body encoding: utf-8")
        try:
            raw_body_bytes = raw_body.encode('utf-8')
            print(f"📦 Re-encoded length: {len(raw_body_bytes)} bytes")
            print(f"📦 Match with original: {len(raw_body_bytes) == len(raw_body.encode('utf-8'))}")
        except Exception as e:
            print(f"❌ Encoding error: {e}")
        
        print("\n" + "=" * 80)
        print("STEP 2: Parse POST data (like PHP $_POST)")
        print("=" * 80)
        
        # Check if POST data is empty (like PHP: empty($_POST))
        if not request.form:
            print("❌ ERROR: POST data is empty (like PHP empty(\$_POST))")
            # Like PHP: http_response_code(400); printf('error: %s', $e->getMessage());
            return "error: POST data is empty", 400
        
        # Parse POST data - use Flask's request.form (equivalent to PHP $_POST)
        # IMPORTANT: Keep flat structure for signature verification (ProDAMUS signs flat keys like products[0][name])
        body_dict_flat = request.form.to_dict()
        
        if not body_dict_flat:
            print("❌ ERROR: Parsed POST data is empty")
            return "error: POST data is empty", 400
        
        print(f"📦 Flat structure (for signature verification): {len(body_dict_flat)} fields")
        print(f"📦 Sample flat keys: {list(body_dict_flat.keys())[:10]}")
        
        # Handle PHP-style arrays like products[0][name]
        # Convert products[0][name]=value to products: {0: {name: value}}
        def parse_php_arrays(data: dict) -> dict:
            """
            Convert PHP array notation to nested dicts.
            Handles: products[0][name], products[0][price], etc.
            """
            result = {}
            for key, value in data.items():
                # Skip empty keys
                if not key:
                    continue
                
                # Check if key contains array notation like products[0][name]
                if '[' in key and ']' in key:
                    try:
                        # Parse products[0][name] -> base='products', indices=['0', 'name']
                        parts = key.split('[')
                        if not parts:
                            result[key] = value
                            continue
                        
                        base_key = parts[0]
                        if not base_key:
                            result[key] = value
                            continue
                        
                        # Extract indices: ['0', 'name'] from ['0]', 'name]']
                        indices = []
                        for part in parts[1:]:
                            if ']' in part:
                                idx = part.rstrip(']')
                                if idx:  # Only add non-empty indices
                                    indices.append(idx)
                            else:
                                # Malformed, treat as regular key
                                result[key] = value
                                break
                        else:
                            # Successfully parsed all indices
                            if not indices:
                                result[key] = value
                            else:
                                # Build nested structure
                                if base_key not in result:
                                    result[base_key] = {}
                                
                                current = result[base_key]
                                # Navigate/create nested dicts
                                for idx in indices[:-1]:
                                    if not isinstance(current, dict):
                                        # Conflict: key exists but is not a dict
                                        current = {}
                                        break
                                    if idx not in current:
                                        current[idx] = {}
                                    current = current[idx]
                                
                                # Set final value
                                if isinstance(current, dict):
                                    current[indices[-1]] = value
                    except Exception as e:
                        # If parsing fails, treat as regular key
                        print(f"⚠️  Error parsing PHP array key '{key}': {e}")
                        result[key] = value
                else:
                    # Regular key, no array notation
                    result[key] = value
            
            return result
        
        print("\n" + "=" * 80)
        print("STEP 3: Extract and verify signature (using FLAT structure)")
        print("=" * 80)
        print("⚠️  IMPORTANT: ProDAMUS signs the FLAT structure (products[0][name]), not nested!")
        print("=" * 80)
        
        # Get signature from header (like PHP: $headers['Sign'])
        # Try both 'Sign' and 'sign' (case-insensitive)
        received_sign = request.headers.get("Sign") or request.headers.get("sign", "")
        print(f"🔐 Signature from header: {received_sign}")
        print(f"🔐 Signature length: {len(received_sign)} chars")
        
        # Check if signature is empty (like PHP: empty($headers['Sign']))
        if not received_sign:
            print("❌ ERROR: Signature not found in header (like PHP empty(\$headers['Sign']))")
            return "error: signature not found", 400
        
        # Remove 'sign' field if it exists in body (shouldn't be there, but just in case)
        # Use FLAT structure for signature verification
        body_dict_for_verification = body_dict_flat.copy()
        if 'sign' in body_dict_for_verification:
            print(f"⚠️  WARNING: 'sign' field found in body_dict, removing it")
            del body_dict_for_verification['sign']
        
        print(f"\n📦 Data for signature verification (FLAT structure):")
        print(f"   Total fields: {len(body_dict_for_verification)}")
        print(f"   Sample keys: {list(body_dict_for_verification.keys())[:10]}")
        
        # Convert dict to JSON string (like the example: post_data = r"""{"date":"...",...}""")
        print(f"\n📋 Converting dict to JSON string (like example code)...")
        import json
        post_data_json = json.dumps(body_dict_for_verification, ensure_ascii=False, separators=(',', ':'))
        print(f"   JSON string length: {len(post_data_json)} chars")
        print(f"   JSON preview (first 300 chars): {post_data_json[:300]}...")
        if len(post_data_json) > 300:
            print(f"   JSON preview (last 100 chars): ...{post_data_json[-100:]}")
        
        # Try to recreate the signature to see if body was modified
        print(f"\n🔍 SIGNATURE INTEGRITY CHECK:")
        try:
            # Calculate what signature SHOULD be based on JSON string (like example code)
            print(f"   Using JSON string for signature calculation (like example: post_data = r\"\"\"...\"\"\")...")
            calculated_sign = HmacPy.create(post_data_json, PRODAMUS_SECRET_KEY)
            print(f"🔐 Calculated signature (from parsed data): {calculated_sign}")
            print(f"🔐 Received signature (from header):        {received_sign}")
            
            if calculated_sign:
                print(f"🔐 Signatures match (case-insensitive): {calculated_sign.lower() == received_sign.lower()}")
                
                if calculated_sign.lower() != received_sign.lower():
                    print(f"\n⚠️  WARNING: Signatures don't match!")
                    print(f"This suggests either:")
                    print(f"  1. The request body was modified by a proxy/gateway")
                    print(f"  2. The secret key is incorrect")
                    print(f"  3. Data parsing is incorrect")
                    
                    # Show first difference
                    calc_lower = calculated_sign.lower()
                    recv_lower = received_sign.lower()
                    min_len = min(len(calc_lower), len(recv_lower))
                    for i in range(min_len):
                        if calc_lower[i] != recv_lower[i]:
                            print(f"  First difference at position {i}: '{calc_lower[i]}' vs '{recv_lower[i]}'")
                            print(f"  Calculated [...{calculated_sign[max(0,i-10):i+10]}...]")
                            print(f"  Received   [...{received_sign[max(0,i-10):i+10]}...]")
                            break
            else:
                print(f"❌ Failed to calculate signature!")
        except Exception as e:
            print(f"⚠️  Could not calculate signature: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n🔍 Calling HmacPy.verify() with JSON string (like example code)...")
        print(f"   - post_data_json type: {type(post_data_json).__name__}")
        print(f"   - post_data_json length: {len(post_data_json)} chars")
        print(f"   - signature: {received_sign[:30]}...")
        
        is_valid = HmacPy.verify(post_data_json, PRODAMUS_SECRET_KEY, received_sign)
        
        print(f"\n🔍 Verification result: {is_valid}")
        
        # Additional debug if verification failed
        if not is_valid:
            print(f"\n🔍 DEBUGGING FAILED VERIFICATION:")
            print(f"📦 Flat body dict sample (first 10 items):")
            for key, value in list(body_dict_for_verification.items())[:10]:
                print(f"   {key}: {value} (type: {type(value).__name__})")
            
            print(f"\n📦 JSON string that was used for verification:")
            print(f"   Length: {len(post_data_json)} chars")
            print(f"   Full JSON: {post_data_json}")
        
        if not is_valid:
            print("\n" + "=" * 80)
            print("❌ SIGNATURE VERIFICATION FAILED")
            print("=" * 80)
            print("⚠️  Webhook REJECTED due to invalid signature")
            print(f"📦 Order ID: {body_dict_for_verification.get('order_id', 'unknown')}")
            print(f"📦 Payment status: {body_dict_for_verification.get('payment_status', 'unknown')}")
            print(f"📦 Sum: {body_dict_for_verification.get('sum', 'unknown')}")
            print(f"📦 Email: {body_dict_for_verification.get('customer_email', 'unknown')}")
            print("=" * 80)
            # Like PHP: http_response_code(400); printf('error: %s', 'signature incorrect');
            return "error: signature incorrect", 400
        
        print("\n✅ SIGNATURE VERIFIED SUCCESSFULLY!")
        
        # Now parse PHP arrays for use in payment handler (nested structure)
        print("\n" + "=" * 80)
        print("STEP 4: Parse PHP arrays for payment processing")
        print("=" * 80)
        print("⚠️  Now converting flat structure to nested for easier processing...")
        
        body_dict = parse_php_arrays(body_dict_flat)
        
        print(f"✅ Parsed PHP arrays successfully!")
        print(f"📊 Total fields after parsing: {len(body_dict)}")
        
        print(f"\n📋 Nested structure sample:")
        for key, value in list(body_dict.items())[:5]:
            if isinstance(value, dict):
                print(f"  {key}: (nested dict with {len(value)} items)")
            else:
                print(f"  {key}: {value}")
        
        print("\n" + "=" * 80)
        print("STEP 5: Check payment status and process")
        print("=" * 80)
        
        # Extract all important fields
        order_id = body_dict.get("order_id", "")
        payment_status = body_dict.get("payment_status", "")
        order_num = body_dict.get("order_num", "")
        payment_sum = body_dict.get("sum", "0")
        customer_email = body_dict.get("customer_email", "")
        customer_phone = body_dict.get("customer_phone", "")
        payment_date = body_dict.get("date", "")
        payment_type = body_dict.get("payment_type", "")
        
        print(f"📋 Order ID: {order_id}")
        print(f"📋 Order Number: {order_num}")
        print(f"💰 Payment Sum: {payment_sum} RUB")
        print(f"📧 Customer Email: {customer_email}")
        print(f"📱 Customer Phone: {customer_phone}")
        print(f"📅 Payment Date: {payment_date}")
        print(f"💳 Payment Type: {payment_type}")
        print(f"✅ Payment Status: {payment_status}")
        
        # Check if products field exists
        if "products" in body_dict:
            print(f"\n📦 Products: {body_dict['products']}")
        
        print(f"\n🔍 Status check: payment_status.lower() = '{payment_status.lower()}'")
        
        if payment_status.lower() == "success":
            print("\n" + "=" * 80)
            print("✅ PAYMENT SUCCESSFUL - GRANTING ACCESS")
            print("=" * 80)
            print(f"👤 Processing payment for order: {order_id}")
            print(f"💵 Amount: {payment_sum} RUB")
            print(f"📧 Email: {customer_email}")
            
            handle_prodamus_payment(bot, body_dict)
            
            print("\n✅ Payment processed successfully!")
            print("=" * 80)
            # Like PHP: http_response_code(200); echo 'success';
            return "success", 200
        else:
            print("\n" + "=" * 80)
            print(f"❌ PAYMENT NOT SUCCESSFUL: {payment_status}")
            print("=" * 80)
            print(f"📋 Order ID: {order_id}")
            print(f"⚠️  Status description: {body_dict.get('payment_status_description', 'N/A')}")
            
            # Still notify about failed payment
            handle_prodamus_payment(bot, body_dict)
            
            print("=" * 80)
            # Still return success to ProDAMUS (we processed the webhook)
            return "success", 200
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        # Like PHP: http_response_code($e->getCode() ? $e->getCode() : 400);
        return f"error: {str(e)}", 400


# Configure Telegram webhook at import time when running under WSGI
if USE_WEBHOOK and WEBHOOK_URL and not WEBHOOK_URL.startswith("https://<"):
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "pre_checkout_query"]
        )
        print(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        print("Failed to set webhook:", e)


if __name__ == "__main__":
    if USE_WEBHOOK:
        print("Webhook mode enabled. Run webhook_app.py (WSGI) on your server.")
    else:
        # Run channel diagnostics on startup
        try:
            startup_report = check_course_channels(bot, get_courses_data)
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, "🔎 Диагностика каналов при старте:\n" + startup_report, disable_web_page_preview=True)
                except Exception:
                    pass
        except Exception as e:
            print("Channel diagnostics failed on startup:", e)
        print("Bot started in polling mode...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
