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
    print("=" * 80)
    print("💰 ProDAMUS: Processing payment webhook")
    print("=" * 80)
    print(f"📦 Webhook data received:")
    for key, value in webhook_data.items():
        if isinstance(value, dict):
            print(f"   {key}: (nested dict with {len(value)} items)")
        else:
            print(f"   {key}: {value}")
    
    order_id = webhook_data.get("order_id", "")
    payment_status = webhook_data.get("payment_status", "")
    payment_sum = webhook_data.get("sum", "0")
    customer_email = webhook_data.get("customer_email", "")
    
    print(f"\n📋 Extracted fields:")
    print(f"   Order ID: {order_id}")
    print(f"   Payment Status: {payment_status}")
    print(f"   Payment Sum: {payment_sum} RUB")
    print(f"   Customer Email: {customer_email}")
    
    # Parse order_id to get user_id and course_id (format: "user_id:course_id")
    print(f"\n📋 Step 1: Parsing order_id")
    print(f"   Order ID format: user_id:course_id")
    try:
        parts = order_id.split(":", 1)
        if len(parts) != 2:
            print(f"❌ Invalid order_id format: {order_id}")
            print(f"   Expected format: user_id:course_id")
            print("=" * 80)
            return
        
        user_id = int(parts[0])
        course_id = parts[1]
        print(f"   ✅ Parsed successfully:")
        print(f"      User ID: {user_id}")
        print(f"      Course ID: {course_id}")
    except ValueError as e:
        print(f"❌ Error: User ID is not a number")
        print(f"   Order ID: {order_id}")
        print(f"   Error: {e}")
        print("=" * 80)
        return
    except Exception as e:
        print(f"❌ Error parsing order_id '{order_id}': {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return
    
    # Get course data
    print(f"\n📋 Step 2: Getting course data")
    try:
        courses = get_courses_data()
        print(f"   Total courses available: {len(courses)}")
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    except Exception as e:
        print(f"❌ Error getting course data: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return
    
    if not course:
        print(f"❌ Course {course_id} not found in catalog")
        print("=" * 80)
        return
    
    course_name = course.get("name", f"ID {course_id}")
    duration = int(course.get("duration_minutes", 0))
    channel = str(course.get("channel", ""))
    
    print(f"   ✅ Course found:")
    print(f"      Name: {course_name}")
    print(f"      Duration: {duration} minutes")
    print(f"      Channel: {channel if channel else '(not set)'}")
    
    # Check if payment was successful
    print(f"\n📋 Step 3: Checking payment status")
    print(f"   Payment status: {payment_status}")
    print(f"   Status (lowercase): {payment_status.lower()}")
    
    if payment_status.lower() == "success":
        # Successful payment - grant access
        print(f"   ✅ Payment successful - granting access")
        print(f"\n📋 Step 4: Granting access to user")
        
        # Ensure user exists in database before adding purchase (to avoid foreign key constraint error)
        print(f"   Checking if user exists in database...")
        add_user(user_id)
        print(f"   ✅ User {user_id} added/updated in database")
        
        # Add purchase to database
        print(f"   Adding purchase to database...")
        expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=order_id)
        print(f"   ✅ Purchase added:")
        print(f"      User ID: {user_id}")
        print(f"      Course ID: {course_id}")
        print(f"      Course Name: {course_name}")
        print(f"      Expiry timestamp: {expiry_ts}")
        print(f"      Payment ID: {order_id}")
        
        # Create invite link
        print(f"\n📋 Step 5: Creating channel invite link")
        invite_link = None
        if channel:
            print(f"   Channel ID: {channel}")
            try:
                invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                invite_link = invite.invite_link
                print(f"   ✅ Invite link created: {invite_link}")
            except Exception as e:
                print(f"   ❌ Failed to create invite link: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⚠️  No channel configured for this course")
        
        # Send success message to user
        print(f"\n📋 Step 6: Sending success message to user")
        clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
        text = PURCHASE_SUCCESS_MSG.format(course_name=clean_course_name)
        if invite_link:
            text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
        
        print(f"   User ID: {user_id}")
        print(f"   Message length: {len(text)} chars")
        print(f"   Has invite link: {invite_link is not None}")
        
        try:
            if invite_link:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                bot.send_message(user_id, text, reply_markup=kb)
                print(f"   ✅ Message sent with invite link button")
            else:
                bot.send_message(user_id, text)
                print(f"   ✅ Message sent (no invite link)")
        except Exception as e:
            print(f"   ❌ Error sending message: {e}")
            import traceback
            traceback.print_exc()
        
        # Notify admins
        print(f"\n📋 Step 7: Notifying admins")
        try:
            amount = float(webhook_data.get("sum", 0))
            buyer_email = webhook_data.get("customer_email", "")
            admin_text = f"💰 Оплата (ProDAMUS): пользователь {user_id} купил {clean_course_name} на сумму {amount:.2f} RUB."
            if buyer_email:
                admin_text += f"\nEmail: {buyer_email}"
            
            print(f"   Admin IDs: {ADMIN_IDS}")
            print(f"   Amount: {amount:.2f} RUB")
            print(f"   Buyer email: {buyer_email if buyer_email else '(not provided)'}")
            
            notified_count = 0
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, admin_text)
                    notified_count += 1
                    print(f"   ✅ Notified admin {aid}")
                except Exception as e:
                    print(f"   ❌ Failed to notify admin {aid}: {e}")
            
            print(f"   ✅ Notified {notified_count}/{len(ADMIN_IDS)} admins")
        except Exception as e:
            print(f"   ❌ Error notifying admins: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n✅ Payment processing completed successfully!")
        print("=" * 80)
            
    else:
        # Failed payment - notify user
        print(f"   ❌ Payment failed - status: {payment_status}")
        print(f"\n📋 Step 4: Handling failed payment")
        
        status_desc = webhook_data.get("payment_status_description", "Неизвестная ошибка")
        print(f"   Status description: {status_desc}")
        print(f"   User ID: {user_id}")
        print(f"   Course ID: {course_id}")
        
        try:
            text = f"❌ Оплата не прошла: {status_desc}\n\nПопробуйте еще раз или выберите другой способ оплаты."
            print(f"   Sending failure notification to user...")
            bot.send_message(user_id, text)
            print(f"   ✅ Failure message sent to user")
        except Exception as e:
            print(f"   ❌ Error sending failure message: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n⚠️  Payment processing completed (failed)")
        print("=" * 80)


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
        print("=" * 80)
        print("💰 ProDAMUS: User clicked ProDAMUS payment button")
        print("=" * 80)
        
        if not ENABLE_PRODAMUS:
            print("❌ ProDAMUS is not enabled in config")
            bot.answer_callback_query(c.id, "ProDAMUS не настроен.", show_alert=True)
            return
        
        user_id = c.from_user.id
        username = getattr(c.from_user, "username", None)
        course_id = c.data.split("_", 2)[2]
        
        print(f"👤 User ID: {user_id}")
        print(f"👤 Username: @{username}" if username else "👤 Username: (not set)")
        print(f"📚 Course ID: {course_id}")
        
        try:
            courses = get_courses_data()
            print(f"📋 Courses loaded: {len(courses)}")
        except Exception as e:
            print(f"❌ Error loading courses: {e}")
            bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
            return
        
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            print(f"❌ Course {course_id} not found in catalog")
            bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
            return
        
        course_name = course.get("name", "Курс")
        course_price = course.get("price", 0)
        print(f"📚 Course found:")
        print(f"   Name: {course_name}")
        print(f"   Price: {course_price} RUB")
        
        if has_active_subscription(user_id, str(course_id)):
            print(f"⚠️  User already has active subscription for this course")
            bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
            return
        
        # Store course_id for this user and ask for email
        print(f"\n📋 Step: Requesting email from user")
        _email_requests[user_id] = {
            "course_id": course_id,
            "step": "waiting_email"
        }
        print(f"   ✅ Stored email request for user {user_id}")
        print(f"   Course ID: {course_id}")
        
        bot.answer_callback_query(c.id)
        bot.send_message(
            user_id,
            "Для оплаты через ProDAMUS необходимо указать ваш email.\n\n"
            "Пожалуйста, отправьте ваш email:\n\n"
            "Отправьте /start чтобы отменить."
        )
        print(f"   ✅ Email request message sent to user")
        print("=" * 80)

    @bot.message_handler(content_types=['text'], func=lambda m: m.from_user.id in _email_requests and _email_requests[m.from_user.id].get("step") == "waiting_email")
    def handle_email_input(message: types.Message):
        """Handle email input from user for ProDAMUS payment"""
        print("=" * 80)
        print("📧 ProDAMUS: User sent email input")
        print("=" * 80)
        
        user_id = message.from_user.id
        email = message.text.strip()
        
        print(f"👤 User ID: {user_id}")
        print(f"📧 Email received: {email}")
        print(f"📧 Email length: {len(email)} chars")
        
        # If user sends a command, cancel email collection
        if email.startswith('/'):
            print(f"⚠️  User sent command '{email}' - canceling email collection")
            del _email_requests[user_id]
            bot.send_message(user_id, "Сбор email отменён. Используйте /start чтобы начать заново.")
            print("=" * 80)
            return
        
        # Basic email validation
        print(f"\n📋 Step 1: Validating email format")
        if "@" not in email:
            print(f"   ❌ Email missing '@' symbol")
            bot.send_message(user_id, "Некорректный email. Попробуйте еще раз:")
            print("=" * 80)
            return
        
        email_parts = email.split("@")
        if len(email_parts) != 2 or "." not in email_parts[1]:
            print(f"   ❌ Email format invalid (missing domain or dot)")
            bot.send_message(user_id, "Некорректный email. Попробуйте еще раз:")
            print("=" * 80)
            return
        
        print(f"   ✅ Email format valid")
        print(f"      Local part: {email_parts[0]}")
        print(f"      Domain: {email_parts[1]}")
        
        # Get course_id from temporary storage
        print(f"\n📋 Step 2: Getting course information")
        course_id = _email_requests[user_id]["course_id"]
        print(f"   Course ID from storage: {course_id}")
        
        try:
            courses = get_courses_data()
            course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        except Exception as e:
            print(f"   ❌ Error loading courses: {e}")
            bot.send_message(user_id, "Не удалось получить данные курса. Попробуйте еще раз.")
            del _email_requests[user_id]
            print("=" * 80)
            return
        
        if not course:
            print(f"   ❌ Course {course_id} not found")
            bot.send_message(user_id, COURSE_NOT_AVAILABLE_MSG)
            del _email_requests[user_id]
            print("=" * 80)
            return
        
        name = course.get("name", "Курс")
        price = float(course.get("price", 0))
        print(f"   ✅ Course found:")
        print(f"      Name: {name}")
        print(f"      Price: {price} RUB")
        
        # Create ProDAMUS payment link
        print(f"\n📋 Step 3: Generating ProDAMUS payment link")
        from payments.prodamus import generate_payment_link
        
        username = getattr(message.from_user, "username", None)
        phone = ""  # Optional, can be left empty
        
        # Create order_id in format "user_id:course_id"
        order_id = f"{user_id}:{course_id}"
        print(f"   Order ID: {order_id}")
        
        # Clean product name for ProDAMUS
        clean_name = strip_html(name)
        customer_extra = f"Покупка курса через Telegram бот"
        if username:
            customer_extra += f" (tg:@{username})"
        
        print(f"   Product name: {clean_name}")
        print(f"   Customer email: {email}")
        print(f"   Customer phone: {phone if phone else '(not provided)'}")
        print(f"   Customer extra: {customer_extra}")
        print(f"   Price: {price} RUB")
        
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
            print(f"\n📋 Step 4: Sending payment link to user")
            del _email_requests[user_id]
            print(f"   ✅ Cleared email request storage")
            
            print(f"   Payment URL: {payment_url}")
            print(f"   URL length: {len(payment_url)} chars")
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 Оплатить", url=payment_url))
            bot.send_message(
                user_id,
                f"Ссылка для оплаты курса \"{clean_name}\" создана!\n\n"
                f"Нажмите кнопку ниже для оплаты:",
                reply_markup=kb
            )
            print(f"   ✅ Payment link sent to user")
            print("=" * 80)
        else:
            # Keep user in email input state so they can retry
            print(f"\n❌ Failed to generate payment link")
            print(f"   User will remain in email input state")
            bot.send_message(user_id, "Ошибка при создании ссылки для оплаты. Попробуйте еще раз, отправив другой email или попробуйте позже.")
            print("=" * 80)

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

