# main.py
"""
Simple Sales Bot - Clean and Modular Version
Main entry point for the bot (polling or webhook mode)
"""

import time
import traceback
import json
from datetime import datetime
import telebot
from flask import Flask, request, abort
from typing import Dict, Any

# #region agent log
def _debug_log(location, message, data=None, hypothesis_id=None):
    try:
        log_entry = {
            "timestamp": int(datetime.now().timestamp() * 1000),
            "location": location,
            "message": message,
            "sessionId": "debug-session",
            "runId": "run1"
        }
        if data is not None:
            log_entry["data"] = data
        if hypothesis_id:
            log_entry["hypothesisId"] = hypothesis_id
        with open("/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass
# #endregion agent log

try:
    _debug_log("main.py:13", "Starting config import", None, "A")
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
    _debug_log("main.py:22", "Config imported successfully", {"has_token": bool(TELEGRAM_BOT_TOKEN), "has_secret": bool(PRODAMUS_SECRET_KEY)}, "A")
except Exception as e:
    _debug_log("main.py:22", "ERROR importing config", {"error": str(e), "error_type": type(e).__name__}, "A")
    raise

# Import handlers
try:
    _debug_log("main.py:25", "Starting handler imports", None, "A")
    from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers
    from handlers.prodamus_hmac import ProdamusHmac
    from handlers.payment_handlers import handle_prodamus_payment
    from utils.channel import check_course_channels
    from google_sheets import get_courses_data
    _debug_log("main.py:30", "Handlers imported successfully", None, "A")
except Exception as e:
    _debug_log("main.py:30", "ERROR importing handlers", {"error": str(e), "error_type": type(e).__name__}, "A")
    raise

# Initialize bot
try:
    _debug_log("main.py:33", "Initializing bot", {"has_token": bool(TELEGRAM_BOT_TOKEN)}, "D")
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)
    _debug_log("main.py:33", "Bot initialized successfully", {"bot_type": str(type(bot))}, "D")
except Exception as e:
    _debug_log("main.py:33", "ERROR initializing bot", {"error": str(e), "error_type": type(e).__name__}, "D")
    raise

# Register all handlers
# IMPORTANT: payment_handlers must be registered FIRST to give priority to email collection
try:
    _debug_log("main.py:37", "Starting handler registration", None, "E")
    payment_handlers.register_handlers(bot)
    basic_handlers.register_handlers(bot)
    catalog_handlers.register_handlers(bot)
    admin_handlers.register_handlers(bot)
    _debug_log("main.py:40", "All handlers registered successfully", None, "E")
except Exception as e:
    _debug_log("main.py:40", "ERROR registering handlers", {"error": str(e), "error_type": type(e).__name__}, "E")
    raise

# Flask app for webhook mode (WSGI server on PythonAnywhere)
try:
    _debug_log("main.py:43", "Creating Flask application", None, "A")
    application = Flask(__name__)
    _debug_log("main.py:43", "Flask application created", {"app_type": str(type(application))}, "A")
except Exception as e:
    _debug_log("main.py:43", "ERROR creating Flask app", {"error": str(e), "error_type": type(e).__name__}, "A")
    raise


@application.get("/")
def _health():
    """Health check endpoint"""
    return "OK", 200


@application.get("/prodamus_webhook")
def _prodamus_webhook_get():
    """Test endpoint for Prodamus webhook (GET request)"""
    return "Prodamus webhook endpoint is active. Use POST method.", 200


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
    """
    Вебхук от Prodamus.

    Эквивалент PHP-кода:

        $headers = apache_request_headers();
        if ( empty($_POST) ) ...
        elseif ( empty($headers['Sign']) ) ...
        elseif ( !Hmac::verify($_POST, $secret_key, $headers['Sign']) ) ...

    Мы поддерживаем два варианта:
      - application/json — тогда берём JSON-объект
      - form-data / x-www-form-urlencoded — тогда берём request.form (аналог $_POST)
    """
    # #region agent log
    _debug_log("main.py:89", "Webhook function entry", None, "B")
    # #endregion agent log
    try:
        # #region agent log
        _debug_log("main.py:105", "Inside try block, accessing request object", {"request_type": str(type(request))}, "C")
        # #endregion agent log
        print("[prodamus_webhook] Webhook received")
        # #region agent log
        _debug_log("main.py:107", "Got request.method", {"method": request.method if hasattr(request, 'method') else 'NO_METHOD'}, "C")
        # #endregion agent log
        print(f"[prodamus_webhook] Method: {request.method}")
        # #region agent log
        _debug_log("main.py:109", "Got request.content_type", {"content_type": request.content_type if hasattr(request, 'content_type') else 'NO_CONTENT_TYPE'}, "C")
        # #endregion agent log
        print(f"[prodamus_webhook] Content-Type: {request.content_type}")
        # Safely log headers
        try:
            # #region agent log
            _debug_log("main.py:110", "Before accessing request.headers", None, "C")
            # #endregion agent log
            headers_dict = {k: v for k, v in request.headers}
            # #region agent log
            _debug_log("main.py:111", "Headers accessed successfully", {"header_count": len(headers_dict)}, "C")
            # #endregion agent log
            print(f"[prodamus_webhook] Headers: {headers_dict}")
        except Exception as e:
            # #region agent log
            _debug_log("main.py:113", "ERROR accessing headers", {"error": str(e), "error_type": type(e).__name__}, "C")
            # #endregion agent log
            print(f"[prodamus_webhook] Could not log headers: {e}")
        
        # #region agent log
        _debug_log("main.py:115", "Checking PRODAMUS_SECRET_KEY", {"has_key": bool(PRODAMUS_SECRET_KEY), "is_changeme": PRODAMUS_SECRET_KEY == "CHANGE_ME" if PRODAMUS_SECRET_KEY else False}, "B")
        # #endregion agent log
        if not PRODAMUS_SECRET_KEY or PRODAMUS_SECRET_KEY == "CHANGE_ME":
            print("[prodamus_webhook] ERROR: secret key not configured")
            return "error: secret key not configured", 500

        # Аналог $headers['Sign'] (проверяем оба варианта регистра)
        # #region agent log
        _debug_log("main.py:120", "Getting signature from headers", None, "B")
        # #endregion agent log
        sign = request.headers.get("Sign") or request.headers.get("sign")
        if not sign:
            # #region agent log
            _debug_log("main.py:122", "Signature not found", {"available_headers": list(request.headers.keys()) if hasattr(request, 'headers') else []}, "B")
            # #endregion agent log
            print("[prodamus_webhook] ERROR: signature not found in headers")
            print(f"[prodamus_webhook] Available headers: {list(request.headers.keys())}")
            return "error: signature not found", 400

        # #region agent log
        _debug_log("main.py:126", "Signature found", {"sign_preview": sign[:20] if sign else None}, "B")
        # #endregion agent log
        print(f"[prodamus_webhook] Signature found: {sign[:20]}...")

        # 1) Пытаемся прочитать JSON (если Prodamus шлёт application/json)
        # #region agent log
        _debug_log("main.py:129", "Before get_json", None, "B")
        # #endregion agent log
        data = request.get_json(silent=True)
        # #region agent log
        _debug_log("main.py:130", "After get_json", {"has_data": data is not None, "data_type": str(type(data))}, "B")
        # #endregion agent log
        print(f"[prodamus_webhook] JSON data: {data is not None}")

        # 2) Если JSON нет — пробуем как форму (аналог $_POST)
        if data is None:
            print("[prodamus_webhook] No JSON data, trying form data")
            form = request.form
            if not form:
                # Попробуем прочитать raw body как строку
                raw_body = request.get_data(as_text=True)
                print(f"[prodamus_webhook] No form data, raw body length: {len(raw_body) if raw_body else 0}")
                if not raw_body or len(raw_body.strip()) == 0:
                    print("[prodamus_webhook] ERROR: POST is empty")
                    return "error: POST is empty", 400
                # Если есть raw body, но нет form, возможно это URL-encoded строка
                try:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(raw_body, keep_blank_values=True)
                    data_dict: Dict[str, Any] = {}
                    for key, values in parsed.items():
                        data_dict[key] = values if len(values) > 1 else values[0]
                    data = data_dict
                    print(f"[prodamus_webhook] Parsed URL-encoded data: {len(data)} fields")
                except Exception as e:
                    print(f"[prodamus_webhook] Failed to parse URL-encoded data: {e}")
                    return "error: POST is empty", 400
            else:
                # Эмуляция $_POST:
                # если у ключа несколько значений, делаем список; если одно — строка
                data_dict: Dict[str, Any] = {}
                for key in form.keys():
                    values = form.getlist(key)
                    data_dict[key] = values if len(values) > 1 else values[0]
                data = data_dict
                print(f"[prodamus_webhook] Parsed form data: {len(data)} fields")

        # Проверяем, что data не пустой и является словарём
        if not data:
            print("[prodamus_webhook] ERROR: data is empty after parsing")
            return "error: POST is empty", 400
        
        if not isinstance(data, dict):
            print(f"[prodamus_webhook] ERROR: data is not a dict, got {type(data)}")
            return "error: invalid data format", 400

        # Теперь data — либо dict/list из JSON, либо dict как $_POST
        # #region agent log
        _debug_log("main.py:175", "Before HMAC verify", {"data_keys": list(data.keys()) if isinstance(data, dict) else "not_dict"}, "B")
        # #endregion agent log
        try:
            is_valid = ProdamusHmac.verify(data, PRODAMUS_SECRET_KEY, sign)
            # #region agent log
            _debug_log("main.py:176", "HMAC verify completed", {"is_valid": is_valid}, "B")
            # #endregion agent log
        except Exception as e:
            # На всякий случай, чтобы проще дебажить
            # #region agent log
            _debug_log("main.py:179", "HMAC verify exception", {"error": str(e), "error_type": type(e).__name__}, "B")
            # #endregion agent log
            print(f"[prodamus_webhook] verify error: {e}")
            traceback.print_exc()
            return "error: internal verify error", 500

        if not is_valid:
            # #region agent log
            _debug_log("main.py:183", "Signature invalid", None, "B")
            # #endregion agent log
            print("[prodamus_webhook] ERROR: signature incorrect")
            return "error: signature incorrect", 400

        # ----- здесь подпись УЖЕ прошла проверку -----
        # Можешь безопасно обрабатывать оплату: создавать заказ, писать в БД и т.п.
        # data тут уже Python-структура (dict/list) после канонизации входа.

        # Пример логирования (аккуратно с персональными данными!)
        print("[prodamus_webhook] valid payment data:", data)

        # Обрабатываем оплату: находим покупателя, выдаём доступ к курсу, отправляем сообщение
        # #region agent log
        _debug_log("main.py:195", "Before handle_prodamus_payment", {"bot_type": str(type(bot))}, "D")
        # #endregion agent log
        try:
            handle_prodamus_payment(bot, data)
            # #region agent log
            _debug_log("main.py:196", "handle_prodamus_payment completed", None, "B")
            # #endregion agent log
            print("[prodamus_webhook] payment processing completed successfully")
            return "success", 200
        except Exception as e:
            # Логируем ошибку и возвращаем 500, чтобы Prodamus повторил запрос
            # #region agent log
            _debug_log("main.py:199", "ERROR in handle_prodamus_payment", {"error": str(e), "error_type": type(e).__name__}, "B")
            # #endregion agent log
            print(f"[prodamus_webhook] ERROR processing payment: {e}")
            traceback.print_exc()
            # Возвращаем 500, чтобы Prodamus повторил запрос позже
            return "error: payment processing failed", 500

    except Exception as e:
        # Общий обработчик ошибок на случай непредвиденных исключений
        # #region agent log
        _debug_log("main.py:206", "FATAL ERROR in webhook", {"error": str(e), "error_type": type(e).__name__}, "B")
        # #endregion agent log
        print(f"[prodamus_webhook] FATAL ERROR: {e}")
        traceback.print_exc()
        # Возвращаем 500, чтобы Prodamus повторил запрос позже
        return "error: internal server error", 500


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
