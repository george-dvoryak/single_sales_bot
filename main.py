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
    ENABLE_PRODAMUS
)

# Import handlers
from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
from utils.channel import check_course_channels
from google_sheets import get_courses_data


# Initialize bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)

# Register all handlers
basic_handlers.register_handlers(bot)
catalog_handlers.register_handlers(bot)
payment_handlers.register_handlers(bot)
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
        from payments.prodamus import verify_webhook_signature, parse_webhook_data, is_payment_successful
        from handlers.payment_handlers import handle_prodamus_payment
        
        # Get signature from header
        signature = request.headers.get("sign", "")
        
        # Get form data
        form_data = request.form.to_dict()
        
        # Verify signature
        if not verify_webhook_signature(form_data, signature):
            print("ProDAMUS webhook: Invalid signature")
            abort(403)
        
        # Parse webhook data
        webhook_data = parse_webhook_data(form_data)
        
        print(f"ProDAMUS webhook received: order_id={webhook_data.get('order_id')}, status={webhook_data.get('payment_status')}")
        
        # Process payment
        handle_prodamus_payment(bot, webhook_data)
        
        return "OK", 200
        
    except Exception as e:
        print(f"Error processing ProDAMUS webhook: {e}")
        import traceback
        traceback.print_exc()
        return "ERROR", 500


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
