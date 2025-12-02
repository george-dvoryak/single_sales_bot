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
        PRODAMUS_SECRET_KEY,
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
    from payments.hmac_prodamus import HmacPy
    from db import add_purchase, add_user, has_active_subscription
    from utils.text_utils import strip_html
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


def build_post_data_string(data: object) -> str:
    """
    Собираем строку post_data ТОЧНО так же,
    как это делает HmacPy внутри (php json_encode + сортировка и т.д.).
    """
    array_data = HmacPy._php_array_cast(data)
    array_data = HmacPy._to_str_values(array_data)
    array_data = HmacPy._sort_recursive(array_data)
    post_data = HmacPy._php_json_encode_unicode(array_data)
    return post_data


@application.post("/prodamus_webhook")
def _prodamus_webhook():
    """Prodamus webhook endpoint with signature verification"""
    try:
        print("[prodamus_webhook] Received POST request")
        
        # 1. Подпись из заголовка
        sign_from_header = request.headers.get("Sign")
        if not sign_from_header:
            print("[prodamus_webhook] ERROR: Missing Sign header")
            abort(400, "Missing Sign header")
        
        if not PRODAMUS_SECRET_KEY:
            print("[prodamus_webhook] ERROR: PRODAMUS_SECRET_KEY not configured")
            abort(500, "Prodamus secret key not configured")
        
        # 2. Достаём данные из тела запроса в том же виде, как их бы видел PHP
        content_type = (request.content_type or "").split(";")[0].strip()
        if content_type == "application/json":
            # Prodamus может прислать JSON
            data_for_sign = request.get_json(force=True, silent=False)
        else:
            # В твоём скрине content-type: application/x-www-form-urlencoded
            # => берём обычную форму (аналог $_POST в PHP)
            form_dict = request.form.to_dict(flat=True)
            # В Prodamus поле products часто приходит JSON‑строкой.
            # В твоём эталонном post_data это массив объектов,
            # поэтому декодируем:
            if "products" in form_dict:
                try:
                    form_dict["products"] = json.loads(form_dict["products"])
                except Exception:
                    # если вдруг это не JSON, просто оставляем строку
                    pass
            data_for_sign = form_dict
        
        # 3. Строка post_data в ТОЧНО таком формате, как в примере
        post_data = build_post_data_string(data_for_sign)
        
        # 4. Проверяем подпись по той же логике, что в твоём примере
        is_valid = HmacPy.verify(post_data, PRODAMUS_SECRET_KEY, sign_from_header)
        if not is_valid:
            print(f"[prodamus_webhook] ERROR: Invalid signature. Sign header: {sign_from_header[:20]}...")
            print(f"[prodamus_webhook] Post data (first 200 chars): {post_data[:200]}...")
            abort(403, "Invalid signature")
        
        # 5. Дальше работаем с данными: распарсим JSON‑строку для удобства
        payload = json.loads(post_data)
        
        print(f"[prodamus_webhook] Signature verified. Payment status: {payload.get('payment_status')}")
        
        # 6. Обработка успешной оплаты
        if payload.get("payment_status") == "success":
            order_num = payload.get("order_num", "")
            order_id = payload.get("order_id", "")
            customer_email = payload.get("customer_email", "")
            sum_amount = payload.get("sum", "0")
            
            print(f"[prodamus_webhook] Processing successful payment: order_num={order_num}, order_id={order_id}")
            
            # Парсим order_num в формате "user_id:course_id"
            # Например: "466513805:1" -> user_id=466513805, course_id=1
            if ":" in order_num:
                try:
                    parts = order_num.split(":", 1)
                    user_id = int(parts[0])
                    course_id = parts[1]
                    
                    # Получаем данные курса
                    try:
                        courses = get_courses_data()
                    except Exception as e:
                        print(f"[prodamus_webhook] ERROR: Could not fetch courses: {e}")
                        courses = []
                    
                    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                    if not course:
                        print(f"[prodamus_webhook] ERROR: Course {course_id} not found")
                        return "OK", 200  # Return OK to Prodamus even if course not found
                    
                    course_name = course.get("name", f"ID {course_id}")
                    duration_days = int(course.get("duration_days", 0)) if course else 0
                    channel = str(course.get("channel", "")) if course else ""
                    
                    # Проверяем, нет ли уже активной подписки
                    if has_active_subscription(user_id, str(course_id)):
                        print(f"[prodamus_webhook] User {user_id} already has active subscription for course {course_id}")
                        return "OK", 200
                    
                    # Добавляем пользователя в БД если его нет
                    try:
                        add_user(user_id, None)
                    except Exception:
                        pass  # User might already exist
                    
                    # Добавляем покупку
                    expiry_ts = add_purchase(
                        user_id,
                        str(course_id),
                        course_name,
                        channel,
                        duration_days,
                        payment_id=f"prodamus_{order_id}"
                    )
                    
                    # Создаём пригласительную ссылку в канал
                    invite_link = None
                    if channel:
                        try:
                            invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                            invite_link = invite.invite_link
                        except Exception as e:
                            print(f"[prodamus_webhook] create_chat_invite_link failed for {channel}: {e}")
                    
                    # Получаем тексты для сообщений
                    try:
                        texts = get_texts_data()
                    except Exception:
                        texts = {}
                    
                    clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
                    purchase_success_msg = texts.get("purchase_success_message", 
                        "Оплата успешно выполнена! Вам предоставлен доступ к курсу {course_name}.")
                    text = purchase_success_msg.format(course_name=clean_course_name)
                    
                    if invite_link:
                        text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
                    
                    purchase_receipt_msg = texts.get("purchase_receipt_message", 
                        "Чек об оплате будет отправлен на ваш email в системе Prodamus.")
                    text += f"\n\n{purchase_receipt_msg}"
                    
                    # Отправляем сообщение пользователю
                    try:
                        if invite_link:
                            kb = telebot.types.InlineKeyboardMarkup()
                            kb.add(telebot.types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                            bot.send_message(user_id, text, reply_markup=kb)
                        else:
                            bot.send_message(user_id, text)
                        print(f"[prodamus_webhook] Success message sent to user {user_id}")
                    except Exception as e:
                        print(f"[prodamus_webhook] ERROR sending message to user {user_id}: {e}")
                    
                    # Уведомляем админов
                    try:
                        amount = float(sum_amount) if sum_amount else 0.0
                        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
                        admin_text = f"💰 Оплата (Prodamus): пользователь {user_id} купил {clean_course_name} на сумму {amount:.2f} RUB."
                        if customer_email:
                            admin_text += f"\nEmail: {customer_email}"
                        admin_text += f"\nOrder ID: {order_id}"
                        for aid in ADMIN_IDS:
                            try:
                                bot.send_message(aid, admin_text)
                            except Exception:
                                pass
                    except Exception as e:
                        print(f"[prodamus_webhook] ERROR notifying admins: {e}")
                    
                except (ValueError, IndexError) as e:
                    print(f"[prodamus_webhook] ERROR parsing order_num '{order_num}': {e}")
                    return "OK", 200  # Return OK to Prodamus even if parsing fails
            else:
                print(f"[prodamus_webhook] WARNING: order_num '{order_num}' does not contain ':' separator")
        
        # Prodamus обычно ждёт просто 200 OK
        return "OK", 200
        
    except Exception as e:
        print(f"[prodamus_webhook] FATAL ERROR: {e}")
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
