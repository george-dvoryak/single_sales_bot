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
from handlers import basic_handlers, catalog_handlers, payment_handlers, admin_handlers, prodamus_hmac
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
    if not PRODAMUS_SECRET_KEY or PRODAMUS_SECRET_KEY == "CHANGE_ME":
        return "error: secret key not configured", 500

    # Аналог $headers['Sign']
    sign = request.headers.get("Sign")
    if not sign:
        return "error: signature not found", 400

    # 1) Пытаемся прочитать JSON (если Prodamus шлёт application/json)
    data = request.get_json(silent=True)

    # 2) Если JSON нет — пробуем как форму (аналог $_POST)
    if data is None:
        form = request.form
        if not form:
            return "error: POST is empty", 400

        # Эмуляция $_POST:
        # если у ключа несколько значений, делаем список; если одно — строка
        data_dict: Dict[str, Any] = {}
        for key in form.keys():
            values = form.getlist(key)
            data_dict[key] = values if len(values) > 1 else values[0]
        data = data_dict

    # Теперь data — либо dict/list из JSON, либо dict как $_POST
    try:
        is_valid = ProdamusHmac.verify(data, PRODAMUS_SECRET_KEY, sign)
    except Exception as e:
        # На всякий случай, чтобы проще дебажить
        print(f"[prodamus_webhook] verify error: {e}")
        return "error: internal verify error", 500

    if not is_valid:
        return "error: signature incorrect", 400

    # ----- здесь подпись УЖЕ прошла проверку -----
    # Можешь безопасно обрабатывать оплату: создавать заказ, писать в БД и т.п.
    # data тут уже Python-структура (dict/list) после канонизации входа.

    # Пример логирования (аккуратно с персональными данными!)
    print("[prodamus_webhook] valid payment data:", data)

    # TODO: вызвать свои функции:
    #   - найти покупателя
    #   - выдать доступ к курсу
    #   - отправить сообщение в Telegram и т.п.

    return "success", 200


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
