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

# Import handlers and supporting utilities
try:
    _debug_log("main.py", "Starting handler and utility imports")
    from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
    from utils.channel import check_course_channels
    from google_sheets import get_courses_data, get_texts_data
    from utils.images import preload_images_for_bot
    from db import has_active_subscription, add_purchase
    from utils.text_utils import strip_html
    from payments.prodamus_sign_formation import sign as prodamus_sign, deep_int_to_string as prodamus_deep_int_to_string
    _debug_log("main.py", "Handlers and utilities imported successfully")
except Exception as e:
    print(f"[main.py] ERROR importing handlers/utilities: {e}")
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

# Preload images from Google Sheets so they are available locally for sending
try:
    _debug_log("main.py", "Starting image preloading")
    texts_for_images = {}
    try:
        texts_for_images = get_texts_data()
    except Exception as e:
        print(f"[main.py] Warning: could not fetch texts for image preloading: {e}")
    preload_images_for_bot(get_courses_data, texts_for_images)
    _debug_log("main.py", "Image preloading completed")
except Exception as e:
    print(f"[main.py] ERROR during image preloading: {e}")

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


@application.post("/prodamus_webhook")
def prodamus_webhook():
    """
    Prodamus webhook endpoint for payment result notifications.
    
    Expects:
    - JSON or form-encoded body with payment data (including signature field)
    - Signature header "Sign" (exact name from Prodamus docs)
    
    Verification steps (strictly following the provided algorithm):
    - Take request contents and convert all values ​​to strings
    - Sort by keys (including nested) in alphabetical order
    - Convert to JSON
    - Escape '/' as '\/'
    - Sign using SHA256 HMAC with secret key
    - Compare with signature from headers
    """
    # #region agent log
    try:
        import json as _agent_json
        import time as _agent_time

        def _agent_debug_log_prodamus(hypothesis_id, location, message, data=None, run_id="initial"):
            try:
                payload = {
                    "sessionId": "debug-session",
                    "runId": run_id,
                    "hypothesisId": hypothesis_id,
                    "location": location,
                    "message": message,
                    "data": data or {},
                    "timestamp": int(_agent_time.time() * 1000),
                }
                with open("/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log", "a", encoding="utf-8") as f:
                    f.write(_agent_json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
    except Exception:
        def _agent_debug_log_prodamus(*args, **kwargs):
            pass
    # #endregion

    try:
        from config import PRODAMUS_SECRET_KEY
        import json
        from handlers.check_signature import HmacPy

        _agent_debug_log_prodamus(
            "H1",
            "main.py:prodamus_webhook",
            "request received",
            {
                "content_type": request.content_type,
                "content_length": request.content_length,
            },
        )

        # Read raw body data as text
        raw_body = request.get_data(as_text=True)
        if not raw_body:
            _agent_debug_log_prodamus(
                "H2",
                "main.py:prodamus_webhook",
                "no raw body",
                {},
            )
            return "NO DATA", 400

        _agent_debug_log_prodamus(
            "H2",
            "main.py:prodamus_webhook",
            "raw body read",
            {"length": len(raw_body)},
        )

        # Try to parse JSON payload
        try:
            data = json.loads(raw_body)
        except Exception as e:
            _agent_debug_log_prodamus(
                "H3",
                "main.py:prodamus_webhook",
                "json parse error",
                {"error": str(e)},
            )
            print("[prodamus_webhook] JSON parse error:", e)
            return "BAD JSON", 400

        if not isinstance(data, dict):
            _agent_debug_log_prodamus(
                "H3",
                "main.py:prodamus_webhook",
                "parsed json is not dict",
                {"type": str(type(data))},
            )
            return "BAD DATA", 400

        _agent_debug_log_prodamus(
            "H3",
            "main.py:prodamus_webhook",
            "parsed json ok",
            {"keys": list(data.keys())},
        )

        # Get signature from headers (case-insensitive)
        header_signature = (
            request.headers.get("Sign")
            or request.headers.get("SIGN")
            or request.headers.get("sign")
            or request.headers.get("X-Sign")
        )
        if not header_signature:
            _agent_debug_log_prodamus(
                "H4",
                "main.py:prodamus_webhook",
                "no signature header",
                {"headers": dict(request.headers)},
            )
            return "NO SIGN HEADER", 400

        _agent_debug_log_prodamus(
            "H4",
            "main.py:prodamus_webhook",
            "signature header found",
            {"header_signature": header_signature},
        )

        # Make copy before transforming for Prodamus helper
        payload = dict(data)

        # Ensure values are strings and sorted, then sign using current Prodamus helper
        prodamus_deep_int_to_string(payload)
        calculated_signature = prodamus_sign(payload, PRODAMUS_SECRET_KEY)

        # Also calculate signature using HmacPy reference implementation on raw JSON body
        hmacpy_signature = HmacPy.create(raw_body, PRODAMUS_SECRET_KEY)
        hmacpy_valid = HmacPy.verify(raw_body, PRODAMUS_SECRET_KEY, header_signature)

        _agent_debug_log_prodamus(
            "H5",
            "main.py:prodamus_webhook",
            "signature comparison",
            {
                "calculated_signature": calculated_signature,
                "header_signature": header_signature,
                "hmacpy_signature": hmacpy_signature,
                "hmacpy_valid": hmacpy_valid,
            },
        )

        # Trust the HmacPy reference implementation as the source of truth.
        # If it says the signature is valid, we accept the webhook even if
        # our older helper (prodamus_sign) disagrees.
        if not hmacpy_valid:
            print("[prodamus_webhook] Signature mismatch (HmacPy invalid)")
            _agent_debug_log_prodamus(
                "H5",
                "main.py:prodamus_webhook",
                "signature mismatch",
                {"calculated_signature": calculated_signature},
            )
            return "INVALID SIGNATURE", 403

        # Business logic: mark purchase as paid if payment_status is success
        payment_status = str(data.get("payment_status", "")).lower()
        if payment_status not in ("success", "paid"):
            # For non-successful statuses, just acknowledge
            print(f"[prodamus_webhook] Non-success status received: {payment_status}")
            _agent_debug_log_prodamus(
                "H6",
                "main.py:prodamus_webhook",
                "non-success status",
                {"payment_status": payment_status},
            )
            return "OK", 200

        # Extract user_id and course_id from order_id.
        # We expect format: "bot-<user_id>-<course_id>" as set in payments.prodamus.build_prodamus_payload
        order_id = str(data.get("order_id", "") or "")
        # Split only into 3 parts: "bot", "<user_id>", "<course_id-with-optional-dashes>"
        parts = order_id.split("-", 2)
        if len(parts) != 3 or parts[0] != "bot":
            print(f"[prodamus_webhook] Invalid order_id format: {order_id}")
            _agent_debug_log_prodamus(
                "H7",
                "main.py:prodamus_webhook",
                "invalid order_id format",
                {"order_id": order_id},
            )
            return "OK", 200

        try:
            user_id = int(parts[1])
        except ValueError:
            print(f"[prodamus_webhook] Invalid user_id in order_id: {order_id}")
            _agent_debug_log_prodamus(
                "H7",
                "main.py:prodamus_webhook",
                "invalid user_id in order_id",
                {"order_id": order_id},
            )
            return "OK", 200

        course_id = parts[2]

        try:
            courses = get_courses_data()
        except Exception as e:
            print("[prodamus_webhook] Error fetching courses:", e)
            _agent_debug_log_prodamus(
                "H8",
                "main.py:prodamus_webhook",
                "error fetching courses",
                {"error": str(e)},
            )
            return "OK", 200

        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            print(f"[prodamus_webhook] Course not found for id={course_id}")
            _agent_debug_log_prodamus(
                "H8",
                "main.py:prodamus_webhook",
                "course not found",
                {"course_id": course_id},
            )
            return "OK", 200

        if has_active_subscription(user_id, str(course_id)):
            print(f"[prodamus_webhook] Subscription already active for user={user_id}, course={course_id}")
            _agent_debug_log_prodamus(
                "H8",
                "main.py:prodamus_webhook",
                "subscription already active",
                {"user_id": user_id, "course_id": course_id},
            )
            return "OK", 200

        course_name = course.get("name", f"ID {course_id}")
        duration_days = int(course.get("duration_days", 0) or 0)
        channel = str(course.get("channel", "") or "")

        payment_id = order_id or ""

        expiry_ts = add_purchase(
            user_id,
            str(course_id),
            course_name,
            channel,
            duration_days,
            payment_id=payment_id,
        )

        invite_link = None
        if channel:
            try:
                invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                invite_link = invite.invite_link
            except Exception as e:
                print(f"[prodamus_webhook] create_chat_invite_link failed for {channel}:", e)

        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        text = f"Оплата через Prodamus успешно выполнена! Вам предоставлен доступ к курсу {clean_course_name}."

        if invite_link:
            text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
            bot.send_message(user_id, text, reply_markup=kb)
        else:
            bot.send_message(user_id, text)

        print(f"[prodamus_webhook] Successfully processed payment for user={user_id}, course={course_id}, expiry={expiry_ts}")
        _agent_debug_log_prodamus(
            "H9",
            "main.py:prodamus_webhook",
            "payment processed successfully",
            {"user_id": user_id, "course_id": course_id, "expiry_ts": expiry_ts},
        )
        return "OK", 200

    except Exception as e:
        print("[prodamus_webhook] ERROR:", e)
        traceback.print_exc()
        _agent_debug_log_prodamus(
            "HEX",
            "main.py:prodamus_webhook",
            "exception",
            {"error": str(e)},
        )
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
