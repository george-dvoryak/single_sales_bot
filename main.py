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
            
            # Try different class names
            if hasattr(prodamuspy, 'PyProdamus'):
                ProdamusClass = prodamuspy.PyProdamus
                print("✅ Found: prodamuspy.PyProdamus")
            elif hasattr(prodamuspy, 'Prodamus'):
                ProdamusClass = prodamuspy.Prodamus
                print("✅ Found: prodamuspy.Prodamus")
            elif hasattr(prodamuspy, 'prodamus'):
                # It might be a submodule
                print("🔍 Found prodamuspy.prodamus submodule, checking...")
                submodule = getattr(prodamuspy, 'prodamus')
                print(f"📦 Submodule attributes: {[a for a in dir(submodule) if not a.startswith('_')]}")
                if hasattr(submodule, 'PyProdamus'):
                    ProdamusClass = submodule.PyProdamus
                    print("✅ Found: prodamuspy.prodamus.PyProdamus")
                else:
                    raise AttributeError(f"Cannot find PyProdamus class. Available in module: {[a for a in dir(prodamuspy) if not a.startswith('_')]}")
            else:
                raise AttributeError(f"Cannot find PyProdamus or Prodamus class. Available in module: {[a for a in dir(prodamuspy) if not a.startswith('_')]}")
                
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
        print(f"📋 Method: {request.method}")
        print(f"📝 Content-Type: {request.content_type}")
        print(f"📏 Content-Length: {request.content_length}")
        
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
        raw_body = request.get_data(as_text=True)
        print(f"📦 Raw body length: {len(raw_body)} bytes")
        print(f"📦 Raw body (first 300 chars):\n{raw_body[:300]}...")
        if len(raw_body) > 300:
            print(f"📦 Raw body (last 100 chars):\n...{raw_body[-100:]}")
        
        print("\n" + "=" * 80)
        print("STEP 2: Parse body with prodamus.parse()")
        print("=" * 80)
        body_dict = prodamus.parse(raw_body)
        print(f"✅ Parsed successfully!")
        print(f"📊 Total fields parsed: {len(body_dict)}")
        print(f"\n📋 All parsed fields:")
        for key, value in sorted(body_dict.items()):
            if isinstance(value, dict):
                print(f"  {key}: (nested dict with {len(value)} items)")
                for nested_key, nested_value in value.items():
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
        
        print(f"\n🔍 Calling prodamus.verify()...")
        print(f"   - body_dict keys: {list(body_dict.keys())}")
        print(f"   - signature: {received_sign[:30]}...")
        
        is_valid = prodamus.verify(body_dict, received_sign)
        
        print(f"\n🔍 Verification result: {is_valid}")
        
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
