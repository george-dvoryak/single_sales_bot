"""Prodamus webhook handler with signature verification."""

import json
import re
import hmac
import hashlib
from typing import Dict, Optional
from flask import request, abort

from config import PRODAMUS_SECRET_KEY, ADMIN_IDS
from db import update_prodamus_payment_status, get_user
from google_sheets import get_courses_data
from handlers import payment_handlers
from utils.logger import log_info, log_error, log_warning


def build_hmac_payload(flat_form: dict) -> dict:
    """
    Convert flat dict with keys like 'products[0][name]' into nested structure.
    
    Similar to PHP $_POST structure:
    {
        ...,
        "products": [
            {"name": "...", "price": "...", ...},
            ...
        ]
    }
    """
    base = {}
    products_tmp = {}  # index -> dict of product fields

    for key, value in flat_form.items():
        # Sign should never participate in signature
        if key == "Sign":
            continue

        match = re.match(r'^products\[(\d+)\]\[(.+)\]$', key)
        if match:
            idx = int(match.group(1))
            field = match.group(2)
            products_tmp.setdefault(idx, {})[field] = value
        else:
            base[key] = value

    if products_tmp:
        # Build products list sorted by index
        base["products"] = [products_tmp[i] for i in sorted(products_tmp.keys())]

    return base


def stringify_recursive(obj) -> Dict:
    """
    Recursively convert all values to strings (PHP array_walk_recursive + strval equivalent).
    """
    if isinstance(obj, dict):
        return {str(k): stringify_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_recursive(v) for v in obj]
    elif obj is None:
        return ""
    else:
        return str(obj)


def sort_recursive(obj) -> Dict:
    """Recursively sort dictionary keys."""
    if isinstance(obj, dict):
        return {
            key: sort_recursive(value)
            for key, value in sorted(obj.items(), key=lambda item: item[0])
        }
    elif isinstance(obj, list):
        return [sort_recursive(item) for item in obj]
    else:
        return obj


def verify_signature(flat_form: dict, provided_signature: str) -> bool:
    """
    Verify Prodamus webhook signature.
    
    Returns True if signature is valid, False otherwise.
    """
    if not PRODAMUS_SECRET_KEY:
        log_error("prodamus_webhook", "PRODAMUS_SECRET_KEY not configured")
        return False
    
    secret_key_bytes = PRODAMUS_SECRET_KEY.encode("utf-8")
    
    # Convert flat dict to nested structure
    payload = build_hmac_payload(flat_form)
    
    # Recursively convert all values to strings
    stringified = stringify_recursive(payload)
    
    # Recursively sort keys
    sorted_payload = sort_recursive(stringified)
    
    # JSON encode without ASCII escaping, with compact separators
    json_string = json.dumps(
        sorted_payload,
        ensure_ascii=False,
        separators=(',', ':')
    )
    
    # PHP json_encode escapes '/' by default, so we mimic this
    msg_to_sign = json_string.replace('/', r'\/')
    
    # Calculate signature
    calculated_signature = hmac.new(
        secret_key_bytes,
        msg=msg_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (constant-time comparison)
    return hmac.compare_digest(
        provided_signature.lower(),
        calculated_signature.lower()
    )


def parse_request_data() -> dict:
    """
    Parse request data from Prodamus webhook.
    Supports both JSON and form-urlencoded content types.
    """
    content_type = (request.content_type or "").split(";")[0].strip()
    
    if content_type == "application/json":
        json_data = request.get_json(force=True, silent=False)
        # Convert JSON to flat form structure
        flat_form = {}
        for key, value in json_data.items():
            if key == "Sign":
                continue
            if key == "products" and isinstance(value, list):
                # Expand products back to flat structure
                for idx, product in enumerate(value):
                    if isinstance(product, dict):
                        for field, field_value in product.items():
                            flat_form[f"products[{idx}][{field}]"] = field_value
            else:
                flat_form[key] = value
        return flat_form
    else:
        # application/x-www-form-urlencoded
        return request.form.to_dict()


def parse_order_num(order_num: str) -> tuple[Optional[int], Optional[str]]:
    """
    Parse order_num in format "user_id_course_id_timestamp".
    
    Returns (user_id, course_id) or (None, None) if parsing fails.
    """
    try:
        parts = order_num.split("_", 2)
        if len(parts) >= 2:
            user_id = int(parts[0])
            course_id = parts[1]
            return user_id, course_id
    except (ValueError, IndexError) as e:
        log_error("prodamus_webhook", f"Failed to parse order_num '{order_num}': {e}")
    
    return None, None


def handle_successful_payment(bot, payload: dict) -> None:
    """Handle successful Prodamus payment."""
    order_num = payload.get("order_num", "")
    order_id = payload.get("order_id", "")
    customer_email = payload.get("customer_email", "")
    sum_amount = payload.get("sum", "0")
    
    log_info("prodamus_webhook", f"Processing successful payment: order_num={order_num}, order_id={order_id}")
    
    user_id, course_id = parse_order_num(order_num)
    if not user_id or not course_id:
        log_warning("prodamus_webhook", f"Could not parse order_num: {order_num}")
        return
    
    # Get course data
    try:
        courses = get_courses_data()
    except Exception as e:
        log_error("prodamus_webhook", f"Could not fetch courses: {e}")
        return
    
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        log_warning("prodamus_webhook", f"Course {course_id} not found")
        return
    
    course_name = course.get("name", f"ID {course_id}")
    duration_days = int(course.get("duration_days", 0)) if course else 0
    channel = str(course.get("channel", "")) if course else ""
    
    log_info("prodamus_webhook", 
             f"Course resolved: id={course_id}, name={course_name}, channel={channel}, duration_days={duration_days}")
    
    # Parse amount
    try:
        amount_float = float(sum_amount) if sum_amount else 0.0
    except (ValueError, TypeError):
        amount_float = 0.0
    
    # Get username for logging
    tg_username = None
    try:
        db_user = get_user(user_id)
        if db_user and "username" in db_user.keys():
            tg_username = db_user["username"]
    except Exception:
        pass
    
    # Grant access and send invite
    payment_handlers.grant_access_and_send_invite(
        bot=bot,
        user_id=user_id,
        course_id=str(course_id),
        course_name=course_name,
        duration_days=duration_days,
        channel=channel,
        payment_id=f"prodamus_{order_id}",
        amount=amount_float,
        currency="RUB",
        buyer_email=customer_email,
        purchase_receipt_msg="Чек об оплате будет отправлен на ваш email в системе Prodamus.",
        admin_prefix="Оплата (Prodamus)",
    )
    
    log_info("prodamus_webhook",
             f"Payment processed: user_id={user_id}, username={tg_username}, email={customer_email}, "
             f"order_id={order_id}, order_num={order_num}")


def handle_failed_payment(bot, payload: dict) -> None:
    """Handle failed Prodamus payment."""
    order_num = payload.get("order_num", "")
    payment_status = payload.get("payment_status", "")
    
    log_info("prodamus_webhook", f"Payment failed: status={payment_status}, order_num={order_num}")
    
    # Parse order_num (legacy format with colon separator)
    if ":" in order_num:
        try:
            parts = order_num.split(":", 1)
            user_id = int(parts[0])
            course_id = parts[1]
            
            # Get course name
            try:
                courses = get_courses_data()
                course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                course_name = course.get("name", f"ID {course_id}") if course else f"ID {course_id}"
            except Exception:
                course_name = f"ID {course_id}"
            
            # Send failed payment message to user
            try:
                failed_msg = (
                    f"❌ Оплата курса \"{course_name}\" не была завершена.\n\n"
                    f"Статус оплаты: {payment_status}\n\n"
                    f"Если вы произвели оплату, но получили это сообщение, пожалуйста, обратитесь в поддержку."
                )
                bot.send_message(user_id, failed_msg)
                log_info("prodamus_webhook", f"Failed payment message sent to user {user_id}")
            except Exception as e:
                log_error("prodamus_webhook", f"Error sending failed payment message to user {user_id}: {e}")
        except (ValueError, IndexError) as e:
            log_error("prodamus_webhook", f"Error parsing order_num for failed payment '{order_num}': {e}")


def notify_admins_invalid_signature(bot, payload_data: dict, provided_signature: str, calculated_signature: str) -> None:
    """Notify admins about invalid webhook signature."""
    try:
        order_id = payload_data.get("order_id", "unknown")
        order_num = payload_data.get("order_num", "unknown")
        payment_status = payload_data.get("payment_status", "unknown")
        
        admin_text = (
            f"⚠️ Prodamus webhook с неподтверждённой подписью!\n\n"
            f"Order ID: {order_id}\n"
            f"Order Num: {order_num}\n"
            f"Payment Status: {payment_status}\n"
            f"Provided Sign: {provided_signature[:20]}...\n"
            f"Calculated Sign: {calculated_signature[:20]}...\n\n"
            f"Данные не обработаны из-за неверной подписи."
        )
        for aid in ADMIN_IDS:
            try:
                bot.send_message(aid, admin_text)
            except Exception:
                pass
    except Exception as e:
        log_error("prodamus_webhook", f"Error notifying admins about invalid signature: {e}")


def process_webhook(bot) -> tuple[str, int]:
    """
    Process Prodamus webhook request.
    
    Returns (response_text, status_code).
    """
    try:
        log_info("prodamus_webhook", "Received POST request")
        
        # Get signature from header
        provided_signature = str(request.headers.get("Sign", "")).strip()
        if not provided_signature:
            log_error("prodamus_webhook", "Missing Sign header")
            abort(400, "Missing Sign header")
        
        # Parse request data
        flat_form = parse_request_data()
        log_info("prodamus_webhook", f"Raw form keys: {list(flat_form.keys())[:10]}...")
        
        # Verify signature
        if not verify_signature(flat_form, provided_signature):
            log_error("prodamus_webhook", "Invalid signature")
            
            # Try to extract payload for admin notification
            try:
                payload = build_hmac_payload(flat_form)
                stringified = stringify_recursive(payload)
                sorted_payload = sort_recursive(stringified)
                json_string = json.dumps(sorted_payload, ensure_ascii=False, separators=(',', ':'))
                msg_to_sign = json_string.replace('/', r'\/')
                calculated_signature = hmac.new(
                    PRODAMUS_SECRET_KEY.encode("utf-8"),
                    msg=msg_to_sign.encode("utf-8"),
                    digestmod=hashlib.sha256
                ).hexdigest()
                notify_admins_invalid_signature(bot, payload, provided_signature, calculated_signature)
            except Exception as e:
                log_error("prodamus_webhook", f"Error preparing admin notification: {e}")
            
            abort(403, "Invalid signature")
        
        log_info("prodamus_webhook", "Signature verified successfully")
        
        # Build payload for processing
        payload = build_hmac_payload(flat_form)
        payment_status = payload.get("payment_status", "")
        order_num = payload.get("order_num", "")
        order_id = payload.get("order_id", "")
        
        log_info("prodamus_webhook", f"Payment status: {payment_status}")
        
        # Update payment status in database
        if order_num:
            try:
                update_prodamus_payment_status(order_num, payment_status)
            except Exception as e:
                log_error("prodamus_webhook", f"Error updating payment status: {e}")
        
        # Handle payment status
        if payment_status == "success":
            handle_successful_payment(bot, payload)
        elif payment_status and payment_status != "success":
            handle_failed_payment(bot, payload)
        
        return "OK", 200
        
    except Exception as e:
        log_error("prodamus_webhook", f"Fatal error: {e}", exc_info=True)
        return "ERROR", 500

