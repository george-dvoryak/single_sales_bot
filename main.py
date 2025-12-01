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
        from payments.prodamus import (
            verify_webhook_signature, 
            parse_webhook_data, 
            is_payment_successful,
            PRODAMUS_LIB_AVAILABLE
        )
        from handlers.payment_handlers import handle_prodamus_payment
        
        # Log incoming webhook for debugging
        print("=" * 60)
        print("ProDAMUS webhook received!")
        print(f"Method: {request.method}")
        print(f"Content-Type: {request.content_type}")
        print(f"Headers: {dict(request.headers)}")
        
        # Get signature from header first
        signature = request.headers.get("sign", "")
        print(f"Signature from header: '{signature}'")
        
        # Get raw body (this is what ProDAMUS sends)
        raw_body = request.get_data(as_text=True)
        print(f"Raw body: {raw_body[:500]}...")  # First 500 chars
        
        # Parse body using prodamuspy library (handles PHP arrays correctly)
        form_data = None
        if PRODAMUS_LIB_AVAILABLE:
            try:
                # Import prodamuspy to parse the body
                import prodamuspy
                print("Using prodamuspy.parse() to parse body...")
                prodamus_parser = prodamuspy.PyProdamus(PRODAMUS_SECRET_KEY)
                form_data = prodamus_parser.parse(raw_body)
                print(f"✅ Parsed with prodamuspy: {len(form_data)} fields")
            except Exception as e:
                print(f"⚠️  prodamuspy parsing error: {e}")
                print("Falling back to request.form.to_dict()...")
                form_data = request.form.to_dict()
        else:
            print("prodamuspy not available, using request.form.to_dict()...")
            form_data = request.form.to_dict()
        
        print(f"Parsed form data keys: {list(form_data.keys())}")
        print(f"Form data sample: {dict(list(form_data.items())[:5])}...")  # First 5 items
        print("=" * 60)
        
        # Check if we have data
        if not form_data:
            print("❌ ERROR: No form data received!")
            return {"error": "No data in request body"}, 400
        
        # Verify signature
        is_valid = verify_webhook_signature(form_data, signature)
        print(f"Signature valid: {is_valid}")
        
        if not is_valid:
            print("=" * 60)
            print("❌ ProDAMUS webhook: Invalid signature - REJECTED")
            print(f"Order ID: {form_data.get('order_id')}")
            print(f"Payment status: {form_data.get('payment_status')}")
            print(f"Customer email: {form_data.get('customer_email')}")
            print(f"Sum: {form_data.get('sum')}")
            print("=" * 60)
            
            # Return error response instead of abort
            return {
                "error": "Invalid signature",
                "message": "Webhook signature verification failed"
            }, 403
        
        # Parse webhook data
        webhook_data = parse_webhook_data(form_data)
        
        print("=" * 60)
        print(f"✅ ProDAMUS webhook ACCEPTED!")
        print(f"Order ID: {webhook_data.get('order_id')}")
        print(f"Payment status: {webhook_data.get('payment_status')}")
        print(f"Sum: {webhook_data.get('sum')}")
        print(f"Customer email: {webhook_data.get('customer_email')}")
        print("=" * 60)
        
        # Process payment
        handle_prodamus_payment(bot, webhook_data)
        
        print("✅ Payment processed successfully")
        return {"status": "ok", "message": "Webhook processed"}, 200
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ Error processing ProDAMUS webhook: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"error": str(e), "message": "Internal server error"}, 500


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
