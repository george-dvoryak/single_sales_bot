# handlers/payment_handlers.py
"""Payment processing handlers."""

import time
import re
from telebot import types
from google_sheets import get_courses_data
from db import (
    has_active_subscription, add_purchase,
    create_prodamus_payment, update_prodamus_payment_url,
    cancel_pending_prodamus_payment,
)
from payments.yookassa import create_invoice, send_receipt_to_tax
from payments.prodamus import generate_order_id, build_payment_link, get_payment_url
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
        """Handle Prodamus payment button click (create link immediately)"""
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

        # Create payment link immediately (no email collection)
        create_prodamus_payment_link(bot, user_id, course_id, course)

    def create_prodamus_payment_link(bot, user_id: int, course_id: str, course: dict):
        """Create Prodamus payment link and send it to user"""
        course_name = course.get("name", "Курс")
        price = float(course.get("price", 0))

        # Maximum age of a pending payment before we force-regenerate (24 hours)
        MAX_PAYMENT_AGE_SEC = 24 * 60 * 60

        # Look up the most recent pending payment for this user+course
        from db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT order_id, payment_url, price, created_at
            FROM prodamus_payments
            WHERE user_id = ? AND course_id = ? AND payment_status = 'pending'
            ORDER BY created_at DESC LIMIT 1;
            """,
            (user_id, course_id),
        )
        existing_payment = cur.fetchone()

        order_id = None
        payment_url = None

        if existing_payment:
            stored_price = existing_payment["price"]
            payment_age = int(time.time()) - (existing_payment["created_at"] or 0)

            price_changed = (stored_price is None) or (abs(stored_price - price) > 0.01)
            too_old = payment_age > MAX_PAYMENT_AGE_SEC

            if price_changed or too_old:
                # Invalidate the stale pending payment
                reason = "price_outdated" if price_changed else "link_expired"
                log_info(
                    "payment_handlers",
                    f"Cancelling stale pending payment for user {user_id}, course {course_id}, "
                    f"order_id={existing_payment['order_id']}, reason={reason}, "
                    f"stored_price={stored_price}, current_price={price}, age_sec={payment_age}",
                )
                cancel_pending_prodamus_payment(existing_payment["order_id"], reason)
                # Will fall through to create a new payment below
            else:
                # Price is valid and payment is fresh
                order_id = existing_payment["order_id"]
                payment_url = existing_payment["payment_url"]
                if payment_url:
                    log_info(
                        "payment_handlers",
                        f"Reusing existing payment for user {user_id}, course {course_id}, order_id={order_id}",
                    )
                # If payment_url is NULL (record exists but URL was never saved) — fall through to generate URL

        # Create a new payment record if we don't have a valid one
        if order_id is None:
            payment_created = False
            for attempt in range(3):
                order_id = generate_order_id(user_id, course_id)
                log_info(
                    "payment_handlers",
                    f"Creating Prodamus payment: user_id={user_id}, course_id={course_id}, "
                    f"order_id={order_id}, price={price}, attempt={attempt + 1}",
                )
                if create_prodamus_payment(order_id, user_id, course_id, "", price=price):
                    payment_created = True
                    break
                if attempt < 2:
                    time.sleep(0.3)
                    log_info("payment_handlers", f"Retrying payment creation for user {user_id}, attempt {attempt + 2}")

            if not payment_created:
                log_error(
                    "payment_handlers",
                    f"Failed to create Prodamus payment after retries: "
                    f"user_id={user_id}, course_id={course_id}, last_order_id={order_id}",
                )
                bot.send_message(user_id, "❌ Ошибка: не удалось создать заказ. Попробуйте позже.")
                return

        try:
            clean_course_name = strip_html(course_name)

            # Generate payment URL if we don't have one yet
            if not payment_url:
                customer_extra = f"Покупка курса через Telegram бот (user_id: {user_id})"
                payment_link = build_payment_link(
                    order_id=order_id,
                    course_name=clean_course_name,
                    price=price,
                    customer_extra=customer_extra,
                )

                bot.send_message(user_id, "⏳ Создаю ссылку на оплату...")
                log_info(
                    "payment_handlers",
                    f"Requesting Prodamus payment URL: user_id={user_id}, course_id={course_id}, "
                    f"order_id={order_id}, link={payment_link[:200]}",
                )
                payment_url = get_payment_url(payment_link)

                if not payment_url:
                    log_error(
                        "payment_handlers",
                        f"Failed to get Prodamus payment URL: user_id={user_id}, course_id={course_id}, "
                        f"order_id={order_id}, link={payment_link[:200]}",
                    )
                    bot.send_message(user_id, "❌ Ошибка при создании ссылки на оплату. Попробуйте позже.")
                    return

                try:
                    update_prodamus_payment_url(order_id, payment_url)
                except Exception as e:
                    log_error(
                        "payment_handlers",
                        f"Error updating Prodamus payment URL in DB: user_id={user_id}, course_id={course_id}, "
                        f"order_id={order_id}, payment_url={payment_url}: {e}",
                        exc_info=True,
                    )

            # Send payment link to user
            text = (
                f"💳 Ссылка на оплату курса \"{clean_course_name}\":\n\n"
                f"{payment_url}\n\n"
                f"После успешной оплаты доступ к курсу будет предоставлен автоматически в течение 5 минут."
            )
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 Перейти к оплате", url=payment_url))
            kb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
            bot.send_message(user_id, text, reply_markup=kb)
            log_info("payment_handlers", f"Payment link sent to user {user_id} for course {course_id}, order_id={order_id}")
        except Exception as e:
            log_error("payment_handlers", f"Error creating payment link for user {user_id}: {e}", exc_info=True)
            bot.send_message(user_id, "❌ Произошла ошибка при создании ссылки на оплату. Попробуйте позже или обратитесь в поддержку.")

