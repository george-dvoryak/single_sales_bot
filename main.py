# main.py
"""
Simple Sales Bot - Clean and Modular Version
Main entry point for the bot (polling or webhook mode)
"""

import time
import traceback
import json
import re
import hmac
import hashlib
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


def build_hmac_payload(flat_form: dict) -> dict:
    """
    Из плоского dict с ключами вида 'products[0][name]'
    собираем структуру как у PHP $_POST:
    {
        ...,
        "products": [
            {"name": "...", "price": "...", ...},
            ...
        ]
    }
    """
    base = {}
    products_tmp = {}  # index -> dict полей продукта

    for key, value in flat_form.items():
        # Sign никогда не должен участвовать в подписи
        if key == "Sign":
            continue

        m = re.match(r'^products\[(\d+)\]\[(.+)\]$', key)
        if m:
            idx = int(m.group(1))
            field = m.group(2)
            products_tmp.setdefault(idx, {})[field] = value
        else:
            base[key] = value

    if products_tmp:
        # Собираем список продуктов по индексу
        base["products"] = [products_tmp[i] for i in sorted(products_tmp.keys())]

    return base


def stringify_recursive(obj):
    """
    Полный аналог array_walk_recursive + strval для PHP:
    все значения (на всех уровнях) превращаем в строки.
    """
    if isinstance(obj, dict):
        return {str(k): stringify_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_recursive(v) for v in obj]
    elif obj is None:
        return ""
    else:
        return str(obj)


def sort_recursive(obj):
    """Рекурсивная сортировка ключей словаря"""
    if isinstance(obj, dict):
        return {
            key: sort_recursive(value)
            for key, value in sorted(obj.items(), key=lambda item: item[0])
        }
    elif isinstance(obj, list):
        return [sort_recursive(item) for item in obj]
    else:
        return obj


@application.post("/prodamus_webhook")
def _prodamus_webhook():
    """Prodamus webhook endpoint with signature verification"""
    try:
        print("[prodamus_webhook] Received POST request")
        
        # 1. Подпись из заголовка
        provided_signature = str(request.headers.get("Sign", "")).strip()
        if not provided_signature:
            print("[prodamus_webhook] ERROR: Missing Sign header")
            abort(400, "Missing Sign header")
        
        if not PRODAMUS_SECRET_KEY:
            print("[prodamus_webhook] ERROR: PRODAMUS_SECRET_KEY not configured")
            abort(500, "Prodamus secret key not configured")
        
        secret_key_bytes = PRODAMUS_SECRET_KEY.encode("utf-8")
        
        # 2. Достаём данные из тела запроса
        content_type = (request.content_type or "").split(";")[0].strip()
        
        if content_type == "application/json":
            # Если пришёл JSON, преобразуем в плоский dict для обработки
            json_data = request.get_json(force=True, silent=False)
            # Преобразуем JSON в форму для единообразной обработки
            flat_form = {}
            for key, value in json_data.items():
                if key == "Sign":
                    continue
                if key == "products" and isinstance(value, list):
                    # Разворачиваем products обратно в плоскую структуру
                    for idx, product in enumerate(value):
                        if isinstance(product, dict):
                            for field, field_value in product.items():
                                flat_form[f"products[{idx}][{field}]"] = field_value
                else:
                    flat_form[key] = value
        else:
            # application/x-www-form-urlencoded - берём плоский dict
            flat_form = request.form.to_dict()
        
        print(f"[prodamus_webhook] Raw form (flat dict): {list(flat_form.keys())[:10]}...")
        
        # 3. Превращаем плоский dict в структуру как у PHP ($_POST)
        payload = build_hmac_payload(flat_form)
        print(f"[prodamus_webhook] Payload for HMAC (nested): {list(payload.keys())}")
        
        # 4. Рекурсивно приводим все значения к строкам
        stringified = stringify_recursive(payload)
        
        # 5. Сортируем ключи рекурсивно
        sorted_payload = sort_recursive(stringified)
        
        # 6. json_encode без экранирования юникода, но со стандартным экранированием '/'
        json_string = json.dumps(
            sorted_payload,
            ensure_ascii=False,
            separators=(',', ':')
        )
        
        # 7. PHP json_encode по умолчанию экранирует '/', поэтому имитируем это
        msg_to_sign = json_string.replace('/', r'\/')
        
        print(f"[prodamus_webhook] Final msg_to_sign (first 200 chars): {msg_to_sign[:200]}...")
        
        # 8. Вычисляем подпись
        calculated_signature = hmac.new(
            secret_key_bytes,
            msg=msg_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        print(f"[prodamus_webhook] Provided signature: {provided_signature[:20]}...")
        print(f"[prodamus_webhook] Calculated signature: {calculated_signature[:20]}...")
        
        # 9. Сравниваем подписи
        if not hmac.compare_digest(
            provided_signature.lower(),
            calculated_signature.lower()
        ):
            print(f"[prodamus_webhook] ERROR: Invalid signature!")
            print(f"[prodamus_webhook] Provided: {provided_signature}")
            print(f"[prodamus_webhook] Calculated: {calculated_signature}")
            print(f"[prodamus_webhook] Message to sign (first 500 chars): {msg_to_sign[:500]}")
            abort(403, "Invalid signature")
        
        print("[prodamus_webhook] Signature verified successfully")
        print(f"[prodamus_webhook] Payment status: {payload.get('payment_status')}")
        
        # 10. Обработка успешной оплаты
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
