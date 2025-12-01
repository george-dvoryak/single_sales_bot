# handlers/payment_handlers.py
"""Payment processing handlers."""

from telebot import types
from google_sheets import get_courses_data, get_texts_data
from db import has_active_subscription, add_purchase, add_user
from payments.yookassa import create_invoice, send_receipt_to_tax
from utils.text_utils import strip_html
from config import ADMIN_IDS, CURRENCY, ENABLE_PRODAMUS

# Dictionary to store temporary email requests: {user_id: {"course_id": ..., "step": "waiting_email"}}
_email_requests = {}


# Load texts
texts = {}
try:
    texts = get_texts_data()
except Exception as e:
    print("Warning: could not fetch texts from Google Sheets:", e)

COURSE_NOT_AVAILABLE_MSG = texts.get("course_not_available_message", "Извините, курс сейчас недоступен.")
PURCHASE_SUCCESS_MSG = texts.get("purchase_success_message", "Оплата успешно выполнена! Вам предоставлен доступ к курсу {course_name}.")
PURCHASE_RECEIPT_MSG = texts.get("purchase_receipt_message", "Чек об оплате будет отправлен на ваш email в системе YooKassa/Мой Налог.")


def handle_prodamus_payment(bot, webhook_data: dict):
    """Handle ProDAMUS payment webhook notification"""
    from payments.prodamus import is_payment_successful
    
    order_id = webhook_data.get("order_id", "")
    payment_status = webhook_data.get("payment_status", "")
    
    # Parse order_id to get user_id and course_id (format: "user_id:course_id")
    try:
        parts = order_id.split(":", 1)
        if len(parts) != 2:
            print(f"ProDAMUS: Invalid order_id format: {order_id}")
            return
        
        user_id = int(parts[0])
        course_id = parts[1]
    except Exception as e:
        print(f"ProDAMUS: Error parsing order_id '{order_id}': {e}")
        return
    
    # Get course data
    try:
        courses = get_courses_data()
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    except Exception as e:
        print(f"ProDAMUS: Error getting course data: {e}")
        return
    
    if not course:
        print(f"ProDAMUS: Course {course_id} not found")
        return
    
    course_name = course.get("name", f"ID {course_id}")
    duration = int(course.get("duration_minutes", 0))
    channel = str(course.get("channel", ""))
    
    if is_payment_successful(webhook_data):
        # Successful payment - grant access
        print(f"ProDAMUS: Successful payment for user {user_id}, course {course_id}")
        
        # Ensure user exists in database before adding purchase (to avoid foreign key constraint error)
        add_user(user_id)
        
        # Add purchase to database
        expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=order_id)
        
        # Create invite link
        invite_link = None
        if channel:
            try:
                invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                invite_link = invite.invite_link
            except Exception as e:
                print(f"ProDAMUS: create_chat_invite_link failed for {channel}: {e}")
        
        # Send success message to user
        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        text = PURCHASE_SUCCESS_MSG.format(course_name=clean_course_name)
        if invite_link:
            text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
        
        try:
            if invite_link:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                bot.send_message(user_id, text, reply_markup=kb)
            else:
                bot.send_message(user_id, text)
        except Exception as e:
            print(f"ProDAMUS: Error sending success message to user {user_id}: {e}")
        
        # Notify admins
        try:
            amount = float(webhook_data.get("sum", 0))
            buyer_email = webhook_data.get("customer_email", "")
            admin_text = f"💰 Оплата (ProDAMUS): пользователь {user_id} купил {clean_course_name} на сумму {amount:.2f} RUB."
            if buyer_email:
                admin_text += f"\nEmail: {buyer_email}"
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, admin_text)
                except Exception:
                    pass
        except Exception as e:
            print(f"ProDAMUS: Error notifying admins: {e}")
            
    else:
        # Failed payment - notify user
        print(f"ProDAMUS: Failed payment for user {user_id}, course {course_id}, status: {payment_status}")
        
        try:
            status_desc = webhook_data.get("payment_status_description", "Неизвестная ошибка")
            text = f"❌ Оплата не прошла: {status_desc}\n\nПопробуйте еще раз или выберите другой способ оплаты."
            bot.send_message(user_id, text)
        except Exception as e:
            print(f"ProDAMUS: Error sending failure message to user {user_id}: {e}")


def register_handlers(bot):
    """Register payment handlers"""
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_yk_"))
    def cb_pay_yk(c: types.CallbackQuery):
        user_id = c.from_user.id
        course_id = c.data.split("_", 2)[2]
        try:
            courses = get_courses_data()
        except Exception:
            bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
            return
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
            return
        if has_active_subscription(user_id, str(course_id)):
            bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
            return

        name = course.get("name", "Курс")
        price = float(course.get("price", 0))
        username = getattr(c.from_user, "username", None)
        
        success = create_invoice(bot, user_id, course_id, name, price, username)
        if success:
            bot.answer_callback_query(c.id)
        else:
            bot.answer_callback_query(c.id, "Ошибка при выставлении счета (ЮKassa).", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_pd_"))
    def cb_pay_prodamus(c: types.CallbackQuery):
        """Handle ProDAMUS payment request - ask for email first"""
        if not ENABLE_PRODAMUS:
            bot.answer_callback_query(c.id, "ProDAMUS не настроен.", show_alert=True)
            return
        
        user_id = c.from_user.id
        course_id = c.data.split("_", 2)[2]
        
        try:
            courses = get_courses_data()
        except Exception:
            bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
            return
        
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
            return
        
        if has_active_subscription(user_id, str(course_id)):
            bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
            return
        
        # Store course_id for this user and ask for email
        _email_requests[user_id] = {
            "course_id": course_id,
            "step": "waiting_email"
        }
        
        bot.answer_callback_query(c.id)
        bot.send_message(
            user_id,
            "Для оплаты через ProDAMUS необходимо указать ваш email.\n\n"
            "Пожалуйста, отправьте ваш email:"
        )

    @bot.message_handler(func=lambda m: m.from_user.id in _email_requests and _email_requests[m.from_user.id].get("step") == "waiting_email")
    def handle_email_input(message: types.Message):
        """Handle email input from user for ProDAMUS payment"""
        user_id = message.from_user.id
        email = message.text.strip()
        
        # Basic email validation
        if "@" not in email or "." not in email.split("@")[1]:
            bot.send_message(user_id, "Некорректный email. Попробуйте еще раз:")
            return
        
        # Get course_id from temporary storage
        course_id = _email_requests[user_id]["course_id"]
        
        try:
            courses = get_courses_data()
            course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        except Exception:
            bot.send_message(user_id, "Не удалось получить данные курса. Попробуйте еще раз.")
            del _email_requests[user_id]
            return
        
        if not course:
            bot.send_message(user_id, COURSE_NOT_AVAILABLE_MSG)
            del _email_requests[user_id]
            return
        
        # Create ProDAMUS payment link
        from payments.prodamus import generate_payment_link
        
        name = course.get("name", "Курс")
        price = float(course.get("price", 0))
        username = getattr(message.from_user, "username", None)
        phone = ""  # Optional, can be left empty
        
        # Create order_id in format "user_id:course_id"
        order_id = f"{user_id}:{course_id}"
        
        # Clean product name for ProDAMUS
        clean_name = strip_html(name)
        customer_extra = f"Покупка курса через Telegram бот"
        if username:
            customer_extra += f" (tg:@{username})"
        
        payment_url = generate_payment_link(
            order_id=order_id,
            customer_email=email,
            customer_phone=phone,
            product_name=clean_name,
            price=price,
            customer_extra=customer_extra
        )
        
        if payment_url:
            # Clear temporary storage only on success
            del _email_requests[user_id]
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 Оплатить", url=payment_url))
            bot.send_message(
                user_id,
                f"Ссылка для оплаты курса \"{clean_name}\" создана!\n\n"
                f"Нажмите кнопку ниже для оплаты:",
                reply_markup=kb
            )
        else:
            # Keep user in email input state so they can retry
            bot.send_message(user_id, "Ошибка при создании ссылки для оплаты. Попробуйте еще раз, отправив другой email или попробуйте позже.")

    @bot.pre_checkout_query_handler(func=lambda q: True)
    def handle_pre_checkout(q: types.PreCheckoutQuery):
        try:
            user_id = q.from_user.id
            payload = q.invoice_payload
            # Payload format: "user_id:course_id"
            parts = payload.split(":", 1)
            if len(parts) < 2:
                bot.answer_pre_checkout_query(q.id, ok=False, error_message="Неверный формат заказа.")
                return
            # Extract course_id (second part), user_id validation not needed here
            cid = parts[1]
            courses = get_courses_data()
            course = next((x for x in courses if str(x.get("id")) == str(cid)), None)
            if course is None:
                bot.answer_pre_checkout_query(q.id, ok=False, error_message=COURSE_NOT_AVAILABLE_MSG)
                return
            if has_active_subscription(user_id, str(cid)):
                bot.answer_pre_checkout_query(q.id, ok=False, error_message="Этот курс уже активен у вас.")
                return
            bot.answer_pre_checkout_query(q.id, ok=True)
        except Exception as e:
            print("pre_checkout error:", e)
            bot.answer_pre_checkout_query(q.id, ok=False, error_message="Ошибка проверки заказа.")

    @bot.message_handler(content_types=['successful_payment'])
    def handle_successful_payment(message: types.Message):
        payment = message.successful_payment
        user_id = message.from_user.id
        payload = payment.invoice_payload
        # Payload format: "user_id:course_id"
        parts = payload.split(":", 1)
        if len(parts) < 2:
            bot.send_message(user_id, "Ошибка: неверный формат заказа. Обратитесь в поддержку.")
            return
        # Extract course_id (second part)
        course_id = parts[1]

        try:
            courses = get_courses_data()
        except Exception:
            courses = []
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        course_name = course.get("name", f"ID {course_id}") if course else f"ID {course_id}"
        duration = int(course.get("duration_minutes", 0)) if course else 0
        channel = str(course.get("channel", "")) if course else ""

        expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=payment.telegram_payment_charge_id)

        invite_link = None
        if channel:
            try:
                invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                invite_link = invite.invite_link
            except Exception as e:
                print(f"create_chat_invite_link failed for {channel}:", e)

        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        text = PURCHASE_SUCCESS_MSG.format(course_name=clean_course_name)
        if invite_link:
            text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
        text += f"\n\n{PURCHASE_RECEIPT_MSG}"

        if invite_link:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
            bot.send_message(user_id, text, reply_markup=kb)
        else:
            bot.send_message(user_id, text)

        # Notify admins
        try:
            amount = payment.total_amount / 100.0
            cur = payment.currency
        except Exception:
            amount, cur = 0, CURRENCY
        buyer_email = None
        try:
            if payment.order_info and payment.order_info.email:
                buyer_email = payment.order_info.email
        except Exception:
            pass
        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        admin_text = f"💰 Оплата: пользователь {user_id} купил {clean_course_name} на сумму {amount:.2f} {cur}."
        if buyer_email:
            admin_text += f"\nEmail: {buyer_email}"
        for aid in ADMIN_IDS:
            try:
                bot.send_message(aid, admin_text)
            except Exception:
                pass

        # Placeholder for sending fiscal receipt (YooKassa auto-fiscalization recommended)
        try:
            # Strip HTML from course name for receipt
            clean_receipt_name = strip_html(course_name) if course_name else f"ID {course_id}"
            send_receipt_to_tax(user_id, clean_receipt_name, amount, buyer_email)
        except Exception as e:
            print("send_receipt_to_tax error:", e)

