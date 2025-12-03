# handlers/payment_handlers.py
"""Payment processing handlers."""

import re
from telebot import types
from google_sheets import get_courses_data
from db import (
    has_active_subscription, add_purchase, add_user,
    create_prodamus_payment, update_prodamus_payment_url
)
from payments.yookassa import create_invoice, send_receipt_to_tax
from payments.prodamus import generate_order_num, build_payment_link, get_payment_url
from utils.text_utils import strip_html
from utils.text_loader import get_text
from utils.logger import log_info, log_error, log_warning
from config import ADMIN_IDS, CURRENCY


COURSE_NOT_AVAILABLE_MSG = get_text("course_not_available_message", "Извините, курс сейчас недоступен.")
PURCHASE_SUCCESS_MSG = get_text("purchase_success_message", "Оплата успешно выполнена! Вам предоставлен доступ к курсу {course_name}.")
PURCHASE_RECEIPT_MSG = get_text("purchase_receipt_message", "Чек об оплате будет отправлен на ваш email в системе YooKassa/Мой Налог.")


def grant_access_and_send_invite(
    bot,
    user_id: int,
    course_id: str,
    course_name: str,
    duration_days: int,
    channel: str,
    payment_id: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
    buyer_email: str | None = None,
    purchase_receipt_msg: str | None = None,
    admin_prefix: str = "Оплата",
):
    """
    Common logic for granting course access, creating invite link,
    notifying user and admins after a successful payment (YooKassa or Prodamus).
    """
    # 1. Add purchase (grant access)
    expiry_ts = add_purchase(
        user_id,
        str(course_id),
        course_name,
        channel,
        duration_days,
        payment_id=payment_id,
    )
    log_info("payments_common", f"Purchase added: user_id={user_id}, course_id={course_id}, expiry_ts={expiry_ts}")

    # 2. Create invite link (if channel configured)
    invite_link = None
    if channel:
        try:
            invite = bot.create_chat_invite_link(
                chat_id=channel,
                member_limit=1,
                expire_date=None,
            )
            invite_link = invite.invite_link
            log_info("payments_common", f"Invite link created: {invite_link}")
        except Exception as e:
            log_error("payments_common", f"create_chat_invite_link failed for {channel}: {e}")

    # 3. Prepare and send message to user
    clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
    receipt_msg = purchase_receipt_msg or PURCHASE_RECEIPT_MSG

    text = PURCHASE_SUCCESS_MSG.format(course_name=clean_course_name)
    if invite_link:
        text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
    text += f"\n\n{receipt_msg}"

    try:
        if invite_link:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
            bot.send_message(user_id, text, reply_markup=kb)
        else:
            bot.send_message(user_id, text)
        log_info("payments_common", f"Success message sent to user {user_id}, invite_link={invite_link}")
    except Exception as e:
        log_error("payments_common", f"Error sending message to user {user_id}: {e}")

    # 4. Notify admins
    try:
        amt = float(amount) if amount is not None else 0.0
        cur = currency or CURRENCY
        admin_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        admin_text = f"💰 {admin_prefix}: пользователь {user_id} купил {admin_course_name} на сумму {amt:.2f} {cur}."
        if buyer_email:
            admin_text += f"\nEmail: {buyer_email}"
        for aid in ADMIN_IDS:
            try:
                bot.send_message(aid, admin_text)
            except Exception:
                pass
    except Exception as e:
        log_error("payments_common", f"Error notifying admins: {e}")


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
            log_error("payment_handlers", f"pre_checkout error: {e}")
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

        # Amount and currency for admin notification
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

        # Use common helper to grant access, send invite & notify admins
        grant_access_and_send_invite(
            bot=bot,
            user_id=user_id,
            course_id=str(course_id),
            course_name=course_name,
            duration_days=duration_days,
            channel=channel,
            payment_id=payment.telegram_payment_charge_id,
            amount=amount,
            currency=cur,
            buyer_email=buyer_email,
            purchase_receipt_msg=PURCHASE_RECEIPT_MSG,
            admin_prefix="Оплата",
        )

        # Placeholder for sending fiscal receipt (YooKassa auto-fiscalization recommended)
        try:
            # Strip HTML from course name for receipt
            clean_receipt_name = strip_html(course_name) if course_name else f"ID {course_id}"
            send_receipt_to_tax(user_id, clean_receipt_name, amount, buyer_email)
        except Exception as e:
            log_error("payment_handlers", f"send_receipt_to_tax error: {e}")

    # Prodamus payment handlers
    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_prodamus_"))
    def cb_pay_prodamus(c: types.CallbackQuery):
        """Handle Prodamus payment button click - ask for email"""
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
        
        # Ask for email
        text = "Для оплаты через Prodamus необходимо указать ваш email адрес.\n\nПожалуйста, отправьте ваш email:"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"course_{course_id}"))
        msg = bot.send_message(user_id, text, reply_markup=kb)
        
        # #region agent log
        import json
        with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A,B,C","location":"payment_handlers.py:250","message":"Initial handler registration","data":{"user_id":user_id,"course_id":course_id,"msg_id":msg.message_id,"msg_chat_id":msg.chat.id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        
        # Register next step handler for email.
        # Using register_next_step_handler with the sent message is more reliable in webhook mode.
        bot.register_next_step_handler(msg, lambda m: handle_prodamus_email(bot, m, course_id))

    def handle_prodamus_email(bot, message: types.Message, course_id: str):
        """Handle email input for Prodamus payment"""
        # #region agent log
        import json
        import time
        with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A,B,C,D,E","location":"payment_handlers.py:258","message":"Handler called","data":{"user_id":message.from_user.id,"message_id":message.message_id,"message_text":message.text[:50] if message.text else None,"course_id":course_id},"timestamp":int(time.time()*1000)}) + '\n')
        # #endregion
        
        user_id = message.from_user.id
        email = message.text.strip() if message.text else ""
        
        # #region agent log
        with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"payment_handlers.py:268","message":"Before email validation","data":{"user_id":user_id,"email":email[:50]},"timestamp":int(time.time()*1000)}) + '\n')
        # #endregion
        
        # Validate email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(email_pattern, email))
        
        # #region agent log
        with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"payment_handlers.py:275","message":"After email validation","data":{"user_id":user_id,"is_valid":is_valid},"timestamp":int(time.time()*1000)}) + '\n')
        # #endregion
        
        if not is_valid:
            text = "❌ Неверный формат email адреса. Пожалуйста, отправьте корректный email:"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"course_{course_id}"))
            
            # #region agent log
            with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"payment_handlers.py:283","message":"Before sending error message","data":{"user_id":user_id,"old_message_id":message.message_id},"timestamp":int(time.time()*1000)}) + '\n')
            # #endregion
            
            error_msg = bot.send_message(user_id, text, reply_markup=kb)
            
            # #region agent log
            with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"payment_handlers.py:289","message":"After sending error message, before re-register","data":{"user_id":user_id,"old_message_id":message.message_id,"new_message_id":error_msg.message_id},"timestamp":int(time.time()*1000)}) + '\n')
            # #endregion
            
            # Re-register next step handler to wait for correct email
            # #region agent log
            with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A,B,E","location":"payment_handlers.py:293","message":"Re-registering handler","data":{"user_id":user_id,"registering_on_old_msg":True,"old_message_id":message.message_id,"new_message_id":error_msg.message_id},"timestamp":int(time.time()*1000)}) + '\n')
            # #endregion
            
            bot.register_next_step_handler(message, lambda m: handle_prodamus_email(bot, m, course_id))
            
            # #region agent log
            with open('/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A,B,E","location":"payment_handlers.py:297","message":"Handler re-registered","data":{"user_id":user_id},"timestamp":int(time.time()*1000)}) + '\n')
            # #endregion
            
            return
        
        try:
            courses = get_courses_data()
        except Exception:
            bot.send_message(user_id, "Ошибка: не удалось получить данные курса.")
            return
        
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            bot.send_message(user_id, COURSE_NOT_AVAILABLE_MSG)
            return
        
        course_name = course.get("name", "Курс")
        price = float(course.get("price", 0))
        
        # Generate order_num in format userId_courseId_timestamp and use it as our main identifier
        order_num = generate_order_num(user_id, course_id)
        order_id = order_num  # store the same value in order_id column for simplicity

        # Try to create payment record once; if DB is locked or duplicate, show error
        if not create_prodamus_payment(order_id, user_id, course_id, email, order_num):
            bot.send_message(user_id, "Ошибка: не удалось создать заказ. Попробуйте позже.")
            return
        
        # Build payment link
        customer_phone = ""  # Optional, can be empty
        customer_extra = f"Покупка курса через Telegram бот (tg:@{message.from_user.username or 'user'})"
        clean_course_name = strip_html(course_name)
        
        payment_link = build_payment_link(
            order_id=order_id,
            order_num=order_num,
            customer_email=email,
            customer_phone=customer_phone,
            course_name=clean_course_name,
            price=price,
            customer_extra=customer_extra
        )
        
        # Get actual payment URL
        bot.send_message(user_id, "⏳ Создаю ссылку на оплату...")
        payment_url = get_payment_url(payment_link)
        
        if not payment_url:
            bot.send_message(user_id, "❌ Ошибка при создании ссылки на оплату. Попробуйте позже.")
            return
        
        # Update payment URL in database
        update_prodamus_payment_url(order_id, payment_url)
        
        # Send payment link to user
        text = f"💳 Ссылка на оплату курса \"{clean_course_name}\":\n\n{payment_url}\n\nПосле успешной оплаты доступ к курсу будет предоставлен автоматически."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Перейти к оплате", url=payment_url))
        kb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
        bot.send_message(user_id, text, reply_markup=kb)

