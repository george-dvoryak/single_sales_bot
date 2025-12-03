# payments/yookassa.py
"""YooKassa payment handler (via Telegram Payments API)."""

import json
from telebot import types
from utils.text_utils import rub_to_kopecks, rub_str, strip_html
from config import PAYMENT_PROVIDER_TOKEN, CURRENCY


def create_invoice(bot, user_id: int, course_id: str, course_name: str, price: float, username: str = None):
    """Create and send YooKassa invoice to user"""
    # Strip HTML from payment label (payment systems don't support HTML in labels)
    payment_label = strip_html(course_name)
    prices = [types.LabeledPrice(label=payment_label, amount=rub_to_kopecks(price))]
    payload = f"{user_id}:{course_id}"

    # Add Telegram username to payment description if available (for YooKassa)
    desc_suffix = f" (tg:@{username})" if username else ""
    # Strip HTML from name for invoice description
    clean_name = strip_html(course_name)
    invoice_description = f'Оплата доступа к курсу "{clean_name}"{desc_suffix}'
    invoice_description = invoice_description[:255]

    # Description for YooKassa payment object
    yk_description = invoice_description[:128]
    yk_metadata = {
        "telegram_user_id": str(user_id),
        "course_id": str(course_id),
    }
    if username:
        yk_metadata["telegram_username"] = f"@{username}"

    # Strip HTML from item description for receipt
    item_description = strip_html(course_name)
    item_description = item_description[:128] if item_description else "Курс"
    provider_data = {
        "description": yk_description,
        "metadata": yk_metadata,
        "receipt": {
            "items": [
                {
                    "description": item_description,
                    "quantity": 1,
                    "amount": {"value": rub_str(price), "currency": CURRENCY},
                    "vat_code": 1
                }
            ]
        }
    }
    provider_data_json = json.dumps(provider_data, ensure_ascii=False)

    # Strip HTML from invoice title
    clean_title_name = strip_html(course_name) if course_name else "Курс"
    try:
        bot.send_invoice(
            user_id,
            title=f"Курс: {clean_title_name}",
            description=invoice_description,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency=CURRENCY,
            prices=prices,
            start_parameter="purchase-course",
            invoice_payload=payload,
            need_email=True,
            send_email_to_provider=True,
            provider_data=provider_data_json
        )
        return True
    except Exception as e:
        from utils.logger import log_error
        log_error("yookassa", f"send_invoice error: {e}")
        return False


def send_receipt_to_tax(user_id: int, course_name: str, amount: float, buyer_email: str = None):
    """Placeholder for 'Мой Налог' integration (YooKassa auto-fiscalization can be enabled in account settings)."""
    from utils.logger import log_info
    log_info("yookassa", f"Receipt: user={user_id}, product='{course_name}', amount={amount}, email={buyer_email}")

