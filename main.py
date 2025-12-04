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
    """Lightweight diagnostics endpoint (requires authentication)"""
    # Require authentication
    if not _require_auth():
        return "Unauthorized", 401
    
    try:
        report = check_course_channels(bot, get_courses_data)
    except Exception as e:
        log_error("diag", f"Diagnostics error: {e}", exc_info=True)
        report = f"diag error: {str(e)}"
    return report, 200


def _sanitize_url(url: str) -> str:
    """Sanitize URL to hide sensitive tokens while preserving useful info"""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        # Hide path if it looks like it contains a token (long path segment)
        if parsed.path and len(parsed.path) > 20:
            # Replace path with masked version
            path_parts = parsed.path.split('/')
            sanitized_parts = []
            for part in path_parts:
                if len(part) > 20:  # Likely a token
                    sanitized_parts.append(f"{part[:4]}...{part[-4:]}" if len(part) > 8 else "***")
                else:
                    sanitized_parts.append(part)
            sanitized_path = '/'.join(sanitized_parts)
            return urlunparse((parsed.scheme, parsed.netloc, sanitized_path, parsed.params, parsed.query, parsed.fragment))
        return url
    except Exception:
        # If parsing fails, return masked version
        if len(url) > 50:
            return f"{url[:20]}...{url[-10:]}"
        return "***"


def _require_auth():
    """Check if request has valid authentication token"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.replace("Bearer ", "").strip()
    # Use WEBHOOK_SECRET_TOKEN as auth token for diagnostic endpoints
    return token == WEBHOOK_SECRET_TOKEN if WEBHOOK_SECRET_TOKEN else False


@application.get("/webhook_info")
def _webhook_info():
    """Check webhook status and configuration (requires authentication)"""
    # Require authentication
    if not _require_auth():
        return "Unauthorized", 401
    
    try:
        import json
        webhook_info = bot.get_webhook_info()
        
        # Sanitize URLs to hide sensitive tokens
        sanitized_webhook_url = _sanitize_url(webhook_info.url) if webhook_info.url else None
        sanitized_config_url = _sanitize_url(WEBHOOK_URL) if WEBHOOK_URL else None
        sanitized_route = _sanitize_url(webhook_route) if webhook_route else None
        
        info = {
            "webhook_url": sanitized_webhook_url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates,
            "configured_route": sanitized_route,
            "webhook_url_config": sanitized_config_url,
            "use_webhook": USE_WEBHOOK,
        }
        return f"Webhook Info:\n{json.dumps(info, indent=2, default=str)}", 200
    except Exception as e:
        log_error("webhook_info", f"Error getting webhook info: {e}", exc_info=True)
        # Don't expose stack trace to client
        return f"Error getting webhook info: {str(e)}", 500


# Webhook endpoint - use WEBHOOK_PATH if set, otherwise use default path
webhook_route = WEBHOOK_PATH if WEBHOOK_PATH else f"/{TELEGRAM_BOT_TOKEN}"


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
            # Log only update_id and message type, not full data (may contain sensitive info)
            try:
                import json
                data = json.loads(json_str)
                update_id = data.get("update_id", "unknown")
                msg_type = "unknown"
                if "message" in data:
                    msg_type = "message"
                elif "callback_query" in data:
                    msg_type = "callback_query"
                elif "pre_checkout_query" in data:
                    msg_type = "pre_checkout_query"
                log_info("webhook", f"Received update: update_id={update_id}, type={msg_type}")
            except Exception:
                # If parsing fails, log minimal info
                log_info("webhook", f"Received data: {len(json_str)} bytes")
            
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
            log_info("main", f"Webhook set to {WEBHOOK_URL}")
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
