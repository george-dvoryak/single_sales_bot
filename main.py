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
        import prodamuspy
        from handlers.payment_handlers import handle_prodamus_payment
        
        print("=" * 60)
        print("ProDAMUS webhook received!")
        
        # Step 0: Init prodamuspy with secret key from .env
        prodamus = prodamuspy.PyProdamus(PRODAMUS_SECRET_KEY)
        print(f"✅ Initialized prodamuspy with secret key")
        
        # Step 1: Get raw body from webhook
        raw_body = request.get_data(as_text=True)
        print(f"Raw body: {raw_body[:200]}...")
        
        # Step 2: Parse body using prodamus.parse()
        body_dict = prodamus.parse(raw_body)
        print(f"✅ Parsed body: {len(body_dict)} fields")
        print(f"Payment status: {body_dict.get('payment_status')}")
        print(f"Order ID: {body_dict.get('order_id')}")
        
        # Step 3: Get signature from header and verify
        received_sign = request.headers.get("sign", "")
        print(f"Received signature: {received_sign[:20]}...")
        
        is_valid = prodamus.verify(body_dict, received_sign)
        print(f"Signature valid: {is_valid}")
        
        if not is_valid:
            print("❌ Invalid signature - REJECTED")
            print("=" * 60)
            return {"error": "Invalid signature"}, 403
        
        print("✅ Signature verified!")
        
        # Step 4: Check payment status and grant access if success
        payment_status = body_dict.get("payment_status", "")
        print(f"Payment status: {payment_status}")
        
        if payment_status.lower() == "success":
            print("✅ Payment successful - granting access")
            print("=" * 60)
            handle_prodamus_payment(bot, body_dict)
            return {"status": "ok"}, 200
        else:
            print(f"❌ Payment not successful: {payment_status}")
            print("=" * 60)
            # Still notify about failed payment
            handle_prodamus_payment(bot, body_dict)
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
