# main.py
"""
Simple Sales Bot - Clean and Modular Version
Main entry point for the bot (polling or webhook mode)
"""

import time
import traceback
import json
import telebot
from flask import Flask, request, abort

# Simple debug logging - only prints, no file I/O to avoid permission issues
def _debug_log(location, message, data=None, hypothesis_id=None):
    """Simple debug logging that only prints - safe for production"""
    try:
        msg = f"[{location}] {message}"
        if data is not None:
            msg += f" | data: {data}"
        print(msg)
    except Exception:
        pass  # Silently fail - don't crash the app if logging fails

try:
    _debug_log("main.py", "Starting config import")
    from config import (
        TELEGRAM_BOT_TOKEN,
        USE_WEBHOOK,
        WEBHOOK_URL,
        WEBHOOK_PATH,
        WEBHOOK_SECRET_TOKEN,
        ADMIN_IDS,
    )
    _debug_log("main.py", "Config imported successfully")
except Exception as e:
    print(f"[main.py] ERROR importing config: {e}")
    raise

# Import handlers
try:
    _debug_log("main.py", "Starting handler imports")
    from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
    from utils.channel import check_course_channels
    from google_sheets import get_courses_data
    _debug_log("main.py", "Handlers imported successfully")
except Exception as e:
    print(f"[main.py] ERROR importing handlers: {e}")
    raise

# Initialize bot
try:
    _debug_log("main.py", "Initializing bot")
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)
    _debug_log("main.py", "Bot initialized successfully")
except Exception as e:
    print(f"[main.py] ERROR initializing bot: {e}")
    raise

# Register all handlers
try:
    _debug_log("main.py", "Starting handler registration")
    payment_handlers.register_handlers(bot)
    basic_handlers.register_handlers(bot)
    catalog_handlers.register_handlers(bot)
    admin_handlers.register_handlers(bot)
    _debug_log("main.py", "All handlers registered successfully")
except Exception as e:
    print(f"[main.py] ERROR registering handlers: {e}")
    raise

# Flask app for webhook mode (WSGI server on PythonAnywhere)
try:
    _debug_log("main.py", "Creating Flask application")
    application = Flask(__name__)
    _debug_log("main.py", "Flask application created")
except Exception as e:
    print(f"[main.py] ERROR creating Flask app: {e}")
    raise


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


@application.get("/webhook_info")
def _webhook_info():
    """Check webhook status and configuration"""
    try:
        webhook_info = bot.get_webhook_info()
        info = {
            "webhook_url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates,
            "configured_route": webhook_route,
            "webhook_url_config": WEBHOOK_URL,
            "use_webhook": USE_WEBHOOK,
        }
        return f"Webhook Info:\n{json.dumps(info, indent=2, default=str)}", 200
    except Exception as e:
        return f"Error getting webhook info: {e}\n{traceback.format_exc()}", 500


# Webhook endpoint - use WEBHOOK_PATH if set, otherwise use default path
webhook_route = WEBHOOK_PATH if WEBHOOK_PATH else f"/{TELEGRAM_BOT_TOKEN}"


@application.post(webhook_route)
def _webhook():
    """Telegram webhook endpoint"""
    try:
        print(f"[webhook] Received POST request to {webhook_route}")
        
        # Validate Telegram secret header if configured
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
            print(f"[webhook] ERROR: Invalid secret token")
            abort(403)
        
        # Read request data
        try:
            raw_data = request.get_data()
            if not raw_data:
                print("[webhook] ERROR: No data received")
                return "ERROR: No data", 400
            
            json_str = raw_data.decode("utf-8")
            print(f"[webhook] Received data: {json_str[:200]}...")  # Log first 200 chars
            
            # Parse and process update
            update = telebot.types.Update.de_json(json_str)
            if update is None:
                print("[webhook] ERROR: Failed to parse update")
                return "ERROR: Invalid update", 400
            
            print(f"[webhook] Processing update: update_id={update.update_id}")
            bot.process_new_updates([update])
            print(f"[webhook] Successfully processed update {update.update_id}")
            
        except Exception as e:
            print(f"[webhook] ERROR processing update: {e}")
            traceback.print_exc()
            return "ERROR", 500
        
        return "OK", 200
        
    except Exception as e:
        print(f"[webhook] FATAL ERROR: {e}")
        traceback.print_exc()
        return "ERROR", 500


# Configure Telegram webhook at import time when running under WSGI
# Wrap in try-except to prevent WSGI import failures
try:
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
            print(f"Failed to set webhook: {e}")
            traceback.print_exc()
except Exception as e:
    print(f"Error in webhook configuration block: {e}")
    traceback.print_exc()


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
