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
        # Try different import methods for prodamuspy
        try:
            import prodamuspy
            print("=" * 80)
            print("🔍 DEBUGGING prodamuspy module")
            print("=" * 80)
            print(f"✅ prodamuspy module imported successfully")
            print(f"📦 Module file: {prodamuspy.__file__ if hasattr(prodamuspy, '__file__') else 'unknown'}")
            print(f"📦 Module version: {prodamuspy.__version__ if hasattr(prodamuspy, '__version__') else 'unknown'}")
            print(f"📦 All attributes in prodamuspy module:")
            for attr in dir(prodamuspy):
                if not attr.startswith('_'):
                    print(f"   - {attr}: {type(getattr(prodamuspy, attr))}")
            print("=" * 80)
            
            # Try different class names (actual class is ProdamusPy, not PyProdamus!)
            if hasattr(prodamuspy, 'ProdamusPy'):
                ProdamusClass = prodamuspy.ProdamusPy
                print("✅ Found: prodamuspy.ProdamusPy")
            elif hasattr(prodamuspy, 'PyProdamus'):
                ProdamusClass = prodamuspy.PyProdamus
                print("✅ Found: prodamuspy.PyProdamus")
            elif hasattr(prodamuspy, 'Prodamus'):
                ProdamusClass = prodamuspy.Prodamus
                print("✅ Found: prodamuspy.Prodamus")
            else:
                raise AttributeError(f"Cannot find Prodamus class. Available in module: {[a for a in dir(prodamuspy) if not a.startswith('_')]}")
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
            return {"error": f"prodamuspy import failed: {e}"}, 500
        except AttributeError as e:
            print(f"❌ Attribute error: {e}")
            return {"error": str(e)}, 500
        
        from handlers.payment_handlers import handle_prodamus_payment
        
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
        print("STEP 0: Initialize prodamuspy library")
        print("=" * 80)
        print(f"🔑 Secret key length: {len(PRODAMUS_SECRET_KEY)} chars")
        print(f"🔑 Secret key (first 10 chars): {PRODAMUS_SECRET_KEY[:10]}...")
        
        prodamus = ProdamusClass(PRODAMUS_SECRET_KEY)
        print("✅ prodamuspy initialized successfully")
        
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
        print("STEP 2: Parse body with prodamus.parse()")
        print("=" * 80)
        body_dict = prodamus.parse(raw_body)
        print(f"✅ Parsed successfully!")
        print(f"📊 Total fields parsed: {len(body_dict)}")
        
        # Check if parsing modified anything
        print(f"\n🔍 PARSING INTEGRITY CHECK:")
        from urllib.parse import parse_qs, urlencode
        
        # Re-encode the parsed dict to see if it matches original
        try:
            # Flatten the dict back to query string (without nested arrays for now)
            flat_dict = {k: str(v) for k, v in body_dict.items() if not isinstance(v, dict)}
            reconstructed = urlencode(sorted(flat_dict.items()))
            print(f"📦 Reconstructed (flat) length: {len(reconstructed)} bytes")
            print(f"📦 Original raw body length: {len(raw_body)} bytes")
            
            # Check if raw_body contains all keys from parsed dict
            print(f"\n🔍 Checking if all parsed keys exist in raw body:")
            for key in list(body_dict.keys())[:5]:  # Check first 5 keys
                if not isinstance(body_dict[key], dict):
                    exists = key in raw_body
                    print(f"  {key}: {'✅' if exists else '❌'} in raw body")
        except Exception as e:
            print(f"⚠️  Could not reconstruct: {e}")
        
        print(f"\n📋 All parsed fields:")
        for key, value in sorted(body_dict.items()):
            if isinstance(value, dict):
                print(f"  {key}: (nested dict with {len(value)} items)")
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, dict):
                        print(f"    {nested_key}: (nested dict with {len(nested_value)} items)")
                        for n2_key, n2_value in list(nested_value.items())[:3]:
                            print(f"      {n2_key}: {n2_value}")
                    else:
                        print(f"    {nested_key}: {nested_value}")
            else:
                print(f"  {key}: {value}")
        
        print("\n" + "=" * 80)
        print("STEP 3: Extract and verify signature")
        print("=" * 80)
        received_sign = request.headers.get("sign", "")
        print(f"🔐 Signature from header: {received_sign}")
        print(f"🔐 Signature length: {len(received_sign)} chars")
        
        if not received_sign:
            print("❌ ERROR: No signature in header!")
            return {"error": "Missing signature"}, 400
        
        # Try to recreate the signature to see if body was modified
        print(f"\n🔍 SIGNATURE INTEGRITY CHECK:")
        try:
            # Calculate what signature SHOULD be based on our parsed data
            calculated_sign = prodamus.sign(body_dict)
            print(f"🔐 Calculated signature (from parsed data): {calculated_sign}")
            print(f"🔐 Received signature (from header):        {received_sign}")
            print(f"🔐 Signatures match: {calculated_sign == received_sign}")
            
            if calculated_sign != received_sign:
                print(f"\n⚠️  WARNING: Signatures don't match!")
                print(f"This suggests either:")
                print(f"  1. The request body was modified by a proxy/gateway")
                print(f"  2. The secret key is incorrect")
                print(f"  3. ProDAMUS is calculating signature differently")
                
                # Show first difference
                for i, (c1, c2) in enumerate(zip(calculated_sign, received_sign)):
                    if c1 != c2:
                        print(f"  First difference at position {i}: '{c1}' vs '{c2}'")
                        print(f"  Calculated [...{calculated_sign[max(0,i-10):i+10]}...]")
                        print(f"  Received   [...{received_sign[max(0,i-10):i+10]}...]")
                        break
        except Exception as e:
            print(f"⚠️  Could not calculate signature: {e}")
        
        print(f"\n🔍 Calling prodamus.verify()...")
        print(f"   - body_dict keys: {list(body_dict.keys())}")
        print(f"   - signature: {received_sign[:30]}...")
        
        is_valid = prodamus.verify(body_dict, received_sign)
        
        print(f"\n🔍 Verification result: {is_valid}")
        
        # Additional debug if verification failed
        if not is_valid:
            print(f"\n🔍 DEBUGGING FAILED VERIFICATION:")
            print(f"📦 Body dict sample (first 5 items):")
            for key, value in list(body_dict.items())[:5]:
                print(f"   {key}: {value} (type: {type(value).__name__})")
            
            # Check if there's a sign field in the body (shouldn't be)
            if 'sign' in body_dict:
                print(f"⚠️  WARNING: 'sign' field found in body_dict!")
                print(f"   This should not be included in verification")
            
            # Try verification with Flask's parsed data
            print(f"\n🔍 Trying verification with Flask's request.form:")
            try:
                is_valid_flask = prodamus.verify(flask_parsed, received_sign)
                print(f"   Verification with Flask data: {is_valid_flask}")
                if is_valid_flask and not is_valid:
                    print(f"   ✅ Flask data verified! Issue is with prodamus.parse()")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            # Try parsing raw body again with different encoding
            print(f"\n🔍 Trying different parsing methods:")
            from urllib.parse import parse_qsl
            try:
                # Method 1: parse_qsl (standard library)
                parsed_qsl = dict(parse_qsl(raw_body, keep_blank_values=True))
                print(f"   parse_qsl result keys: {list(parsed_qsl.keys())[:5]}")
                is_valid_qsl = prodamus.verify(parsed_qsl, received_sign)
                print(f"   Verification with parse_qsl: {is_valid_qsl}")
                if is_valid_qsl:
                    print(f"   ✅ parse_qsl worked! Issue is with prodamus.parse()")
            except Exception as e:
                print(f"   ❌ parse_qsl error: {e}")
        
        if not is_valid:
            print("\n" + "=" * 80)
            print("❌ SIGNATURE VERIFICATION FAILED")
            print("=" * 80)
            print("⚠️  Webhook REJECTED due to invalid signature")
            print(f"📦 Order ID: {body_dict.get('order_id')}")
            print(f"📦 Payment status: {body_dict.get('payment_status')}")
            print(f"📦 Sum: {body_dict.get('sum')}")
            print(f"📦 Email: {body_dict.get('customer_email')}")
            print("=" * 80)
            return {"error": "Invalid signature"}, 403
        
        print("\n✅ SIGNATURE VERIFIED SUCCESSFULLY!")
        
        print("\n" + "=" * 80)
        print("STEP 4: Check payment status and process")
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
            return {"status": "ok", "order_id": order_id}, 200
        else:
            print("\n" + "=" * 80)
            print(f"❌ PAYMENT NOT SUCCESSFUL: {payment_status}")
            print("=" * 80)
            print(f"📋 Order ID: {order_id}")
            print(f"⚠️  Status description: {body_dict.get('payment_status_description', 'N/A')}")
            
            # Still notify about failed payment
            handle_prodamus_payment(bot, body_dict)
            
            print("=" * 80)
            return {"status": "ok", "payment_status": payment_status}, 200
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"error": str(e)}, 500


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
