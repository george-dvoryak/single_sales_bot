# main.py
"""
Simple Sales Bot - Clean and Modular Version
Main entry point for the bot (polling or webhook mode)
"""

import time
import traceback
import telebot
from flask import Flask, request

from utils.logger import log_info, log_error, log_warning

try:
    log_info("main", "Starting config import")
    from config import (
        TELEGRAM_BOT_TOKEN,
        USE_WEBHOOK,
        WEBHOOK_URL,
        WEBHOOK_PATH,
        WEBHOOK_SECRET_TOKEN,
        ADMIN_IDS,
    )
    log_info("main", "Config imported successfully")
except Exception as e:
    log_error("main", f"Error importing config: {e}")
    raise

# Import handlers and supporting utilities
try:
    log_info("main", "Starting handler and utility imports")
    from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
    from utils.channel import check_course_channels
    from google_sheets import get_courses_data
    from utils.images import preload_images_for_bot
    from utils.text_loader import get_texts
    log_info("main", "Handlers and utilities imported successfully")
except Exception as e:
    log_error("main", f"Error importing handlers/utilities: {e}")
    raise

# Initialize bot
try:
    log_info("main", "Initializing bot")
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)
    log_info("main", "Bot initialized successfully")
except Exception as e:
    log_error("main", f"Error initializing bot: {e}")
    raise

# Register all handlers
try:
    log_info("main", "Starting handler registration")
    payment_handlers.register_handlers(bot)
    basic_handlers.register_handlers(bot)
    catalog_handlers.register_handlers(bot)
    admin_handlers.register_handlers(bot)
    log_info("main", "All handlers registered successfully")
except Exception as e:
    log_error("main", f"Error registering handlers: {e}")
    raise

# Preload images from Google Sheets so they are available locally for sending
try:
    log_info("main", "Starting image preloading")
    texts_for_images = get_texts()
    preload_images_for_bot(get_courses_data, texts_for_images)
    log_info("main", "Image preloading completed")
except Exception as e:
    log_warning("main", f"Error during image preloading: {e}")

# Flask app for webhook mode (WSGI server on PythonAnywhere)
try:
    log_info("main", "Creating Flask application")
    application = Flask(__name__)
    log_info("main", "Flask application created")
except Exception as e:
    log_error("main", f"Error creating Flask app: {e}")
    raise


@application.get("/")
def _health():
    """Health check endpoint"""
    return "OK", 200


@application.get("/diag")
def _diag():
    """
    Lightweight diagnostics endpoint.
    SECURITY: This endpoint exposes channel configuration info.
    Consider adding authentication in production.
    """
    try:
        report = check_course_channels(bot, get_courses_data)
    except Exception as e:
        report = f"diag error: {e}"
    return report, 200


@application.get("/webhook_info")
def _webhook_info():
    """Check webhook status and configuration (sanitized for security)"""
    try:
        import json
        webhook_info = bot.get_webhook_info()
        
        # SECURITY: Sanitize webhook URL to not expose token
        webhook_url_sanitized = webhook_info.url
        if webhook_url_sanitized and TELEGRAM_BOT_TOKEN in webhook_url_sanitized:
            # Replace token in URL with [REDACTED]
            webhook_url_sanitized = webhook_url_sanitized.replace(TELEGRAM_BOT_TOKEN, "[REDACTED]")
        
        # SECURITY: Sanitize configured route
        route_sanitized = webhook_route
        if route_sanitized and TELEGRAM_BOT_TOKEN in route_sanitized:
            route_sanitized = route_sanitized.replace(TELEGRAM_BOT_TOKEN, "[REDACTED]")
        
        # SECURITY: Sanitize WEBHOOK_URL config
        webhook_url_config_sanitized = WEBHOOK_URL
        if webhook_url_config_sanitized and TELEGRAM_BOT_TOKEN in webhook_url_config_sanitized:
            webhook_url_config_sanitized = webhook_url_config_sanitized.replace(TELEGRAM_BOT_TOKEN, "[REDACTED]")
        
        info = {
            "webhook_url": webhook_url_sanitized,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates,
            "configured_route": route_sanitized,
            "webhook_url_config": webhook_url_config_sanitized,
            "use_webhook": USE_WEBHOOK,
        }
        return f"Webhook Info:\n{json.dumps(info, indent=2, default=str)}", 200
    except Exception as e:
        log_error("webhook_info", f"Error getting webhook info: {e}", exc_info=True)
        return f"Error getting webhook info: {e}\n{traceback.format_exc()}", 500


# Webhook endpoint - use WEBHOOK_PATH if set, otherwise generate secure path
if not WEBHOOK_PATH:
    # SECURITY: Generate secure random path instead of using bot token
    import hashlib
    # Use first 16 chars of SHA256 hash of token as path (secure but deterministic)
    token_hash = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).hexdigest()[:16]
    webhook_route = f"/webhook_{token_hash}"
else:
    webhook_route = WEBHOOK_PATH


@application.post(webhook_route)
def _webhook():
    """Telegram webhook endpoint"""
    try:
        log_info("webhook", f"Received POST request to {webhook_route}")
        
        # Validate Telegram secret header if configured
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
            log_error("webhook", "Invalid secret token")
            return "Forbidden", 403
        
        # Read request data
        try:
            raw_data = request.get_data()
            if not raw_data:
                log_error("webhook", "No data received")
                return "ERROR: No data", 400
            
            json_str = raw_data.decode("utf-8")
            log_info("webhook", f"Received data: {json_str[:200]}...")
            
            # Parse and process update
            update = telebot.types.Update.de_json(json_str)
            if update is None:
                log_error("webhook", "Failed to parse update")
                return "ERROR: Invalid update", 400
            
            log_info("webhook", f"Processing update: update_id={update.update_id}")
            bot.process_new_updates([update])
            log_info("webhook", f"Successfully processed update {update.update_id}")
            
        except Exception as e:
            log_error("webhook", f"Error processing update: {e}", exc_info=True)
            return "ERROR", 500
        
        return "OK", 200
        
    except Exception as e:
        log_error("webhook", f"Fatal error: {e}", exc_info=True)
        return "ERROR", 500


@application.post("/prodamus_webhook")
def _prodamus_webhook():
    """Prodamus webhook endpoint with signature verification"""
    from payments.prodamus_webhook import process_webhook
    return process_webhook(bot)


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
            # SECURITY: Sanitize webhook URL in logs
            webhook_url_log = WEBHOOK_URL
            if TELEGRAM_BOT_TOKEN in webhook_url_log:
                webhook_url_log = webhook_url_log.replace(TELEGRAM_BOT_TOKEN, "[REDACTED]")
            log_info("main", f"Webhook set to {webhook_url_log}")
        except Exception as e:
            log_error("main", f"Failed to set webhook: {e}", exc_info=True)
except Exception as e:
    log_error("main", f"Error in webhook configuration block: {e}", exc_info=True)


if __name__ == "__main__":
    if USE_WEBHOOK:
        log_info("main", "Webhook mode enabled. Run webhook_app.py (WSGI) on your server.")
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
            log_warning("main", f"Channel diagnostics failed on startup: {e}")
        log_info("main", "Bot started in polling mode...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
