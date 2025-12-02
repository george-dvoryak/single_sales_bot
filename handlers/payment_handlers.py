# handlers/payment_handlers.py
"""Payment processing handlers."""

from telebot import types
from google_sheets import get_courses_data, get_texts_data
from db import has_active_subscription, add_purchase, add_user
from payments.yookassa import create_invoice, send_receipt_to_tax
from payments.prodamus import create_prodamus_payment_link
from utils.text_utils import strip_html
from utils.keyboards import create_course_buttons
from config import ADMIN_IDS, CURRENCY, ENABLE_PRODAMUS


# Load texts
texts = {}
try:
    texts = get_texts_data()
except Exception as e:
    print("Warning: could not fetch texts from Google Sheets:", e)

COURSE_NOT_AVAILABLE_MSG = texts.get("course_not_available_message", "Извините, курс сейчас недоступен.")
PURCHASE_SUCCESS_MSG = texts.get("purchase_success_message", "Оплата успешно выполнена! Вам предоставлен доступ к курсу {course_name}.")
PURCHASE_RECEIPT_MSG = texts.get("purchase_receipt_message", "Чек об оплате будет отправлен на ваш email в системе YooKassa/Мой Налог.")


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

    if ENABLE_PRODAMUS:

        @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_pr_"))
        def cb_pay_pr(c: types.CallbackQuery):
            """Start Prodamus payment flow by asking for email."""
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

            bot.answer_callback_query(c.id)

            # Ask for email with back button
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Назад к оплате", callback_data=f"back_pay_{course_id}"))

            msg = bot.send_message(
                user_id,
                "Введите, пожалуйста, ваш email для получения чека и доступа к материалам:",
                reply_markup=kb,
            )

            # Store course_id in the next step via closure
            bot.register_next_step_handler(msg, _handle_prodamus_email, course_id)


        def _handle_prodamus_email(message: types.Message, course_id: str):
            """Validate email and send Prodamus payment link."""
            user_id = message.from_user.id
            text = (message.text or "").strip()

            # Simple email validation
            import re

            email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(email_regex, text):
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("⬅️ Назад к оплате", callback_data=f"back_pay_{course_id}"))
                msg = bot.send_message(
                    user_id,
                    "Похоже, это не похоже на email. Пожалуйста, отправьте корректный email:",
                    reply_markup=kb,
                )
                bot.register_next_step_handler(msg, _handle_prodamus_email, course_id)
                return

            email = text

            try:
                courses = get_courses_data()
            except Exception:
                bot.send_message(user_id, "Не удалось получить данные курса. Попробуйте позже.")
                return

            course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
            if not course:
                bot.send_message(user_id, COURSE_NOT_AVAILABLE_MSG)
                return

            # Create payment link via Prodamus
            try:
                link = create_prodamus_payment_link(course, email, user_id)
            except Exception as e:
                print("Prodamus link error:", e)
                bot.send_message(user_id, "Ошибка при создании ссылки оплаты Prodamus. Попробуйте позже.")
                return

            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Оплатить", url=link))
            kb.add(types.InlineKeyboardButton("⬅️ Назад к оплате", callback_data=f"back_pay_{course_id}"))

            bot.send_message(
                user_id,
                "Ссылка на оплату (Prodamus):",
                reply_markup=kb,
                disable_web_page_preview=True,
            )

        @bot.callback_query_handler(func=lambda c: c.data.startswith("back_pay_"))
        def cb_back_pay(c: types.CallbackQuery):
            """Return from email/payment step back to course payment buttons."""
            user_id = c.from_user.id
            course_id = c.data.split("_", 2)[2]

            try:
                courses = get_courses_data()
            except Exception:
                bot.answer_callback_query(c.id, "Не удалось загрузить курс.", show_alert=True)
                return

            course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
            if not course:
                bot.answer_callback_query(c.id, "Курс не найден.", show_alert=True)
                return

            name = course.get("name", "")
            desc = course.get("description", "")
            price = course.get("price", 0)
            duration_days = int(course.get("duration_days", 0) or 0)

            formatted_name = strip_html(name) if name else "Курс"
            clean_desc = strip_html(desc) if desc else ""
            if duration_days > 0:
                access_text = f"Доступ: {duration_days} дн."
            else:
                access_text = "Доступ: без ограничения по времени"

            text = f"{formatted_name}\n{clean_desc}\n\nЦена: {price} руб.\n{access_text}"
            ikb = create_course_buttons(course_id)

            bot.send_message(user_id, text, reply_markup=ikb)
            bot.answer_callback_query(c.id)

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
        duration_days = int(course.get("duration_days", 0)) if course else 0
        channel = str(course.get("channel", "")) if course else ""

        expiry_ts = add_purchase(
            user_id,
            str(course_id),
            course_name,
            channel,
            duration_days,
            payment_id=payment.telegram_payment_charge_id
        )

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

