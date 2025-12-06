# handlers/basic_handlers.py
"""Basic command and message handlers."""

import datetime
from telebot import types
from db import get_active_subscriptions
from config import OFERTA_URL
from utils.keyboards import get_main_menu_keyboard
from utils.text_utils import strip_html, format_for_telegram_html
from utils.images import get_local_image_path
from utils.text_loader import get_text
from utils.logger import log_error, log_warning, log_info

WELCOME_MSG = get_text("welcome_message", "Здравствуйте! Этот бот поможет вам купить курсы по макияжу.\nНиже находится меню.")
SUPPORT_MSG = get_text("support_message", "Если у вас есть вопросы, напишите нам в поддержку.")


def register_handlers(bot):
    """Register all basic handlers"""
    
    @bot.message_handler(commands=['start'])
    def handle_start(message: types.Message):
        user_id = message.from_user.id

        # Use dynamic keyboard that includes admin buttons if user is admin
        keyboard = get_main_menu_keyboard(user_id)
        from utils.text_loader import get_texts
        texts = get_texts()
        welcome_image_url = texts.get("welcome_image_url")
        # Format welcome message with HTML support
        formatted_welcome = format_for_telegram_html(WELCOME_MSG)
        try:
            if welcome_image_url:
                local_path = get_local_image_path(welcome_image_url)
                if local_path:
                    try:
                        with open(local_path, "rb") as photo:
                            bot.send_photo(user_id, photo, caption=formatted_welcome, reply_markup=keyboard, parse_mode='HTML')
                    except Exception as e:
                        log_warning("basic_handlers", f"send_photo local welcome image failed: {e}")
                        # Fallback to URL if local file send fails
                        bot.send_photo(user_id, welcome_image_url, caption=formatted_welcome, reply_markup=keyboard, parse_mode='HTML')
                else:
                    # Fallback to sending by URL if cache/download failed
                    bot.send_photo(user_id, welcome_image_url, caption=formatted_welcome, reply_markup=keyboard, parse_mode='HTML')
            else:
                bot.send_message(user_id, formatted_welcome, reply_markup=keyboard, parse_mode='HTML')
        except Exception as e:
            log_warning("basic_handlers", f"send_photo welcome failed, fallback to text: {e}")
            bot.send_message(user_id, formatted_welcome, reply_markup=keyboard, parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.text == "Активные подписки")
    def handle_active(message: types.Message):
        user_id = message.from_user.id
        subs = get_active_subscriptions(user_id)
        subs = list(subs) if subs else []
        if not subs:
            bot.send_message(user_id, "У вас нет активных подписок.")
            return
        
        text = "Ваши активные подписки:\n\n"
        
        for s in subs:
            course_name = s["course_name"]
            clean_course_name = strip_html(course_name) if course_name else "Курс"
            expiry_ts = s["expiry"]
            dt = datetime.datetime.fromtimestamp(expiry_ts)
            dstr = dt.strftime("%Y-%m-%d")
            text += f"• {clean_course_name}\n  Доступ до {dstr}\n\n"
        
        bot.send_message(user_id, text, disable_web_page_preview=True)

    @bot.message_handler(func=lambda m: m.text == "Поддержка")
    def handle_support(message: types.Message):
        user_id = message.from_user.id
        formatted_support = format_for_telegram_html(SUPPORT_MSG)
        bot.send_message(user_id, formatted_support, parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.text == "Оферта")
    def handle_oferta(message: types.Message):
        user_id = message.from_user.id
        try:
            bot.send_document(user_id, OFERTA_URL, caption="Договор оферты (PDF)")
        except Exception:
            # Fallback: send link if Telegram couldn't download the file
            bot.send_message(user_id, f"Договор оферты: {OFERTA_URL}", disable_web_page_preview=False)

