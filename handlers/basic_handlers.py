# handlers/basic_handlers.py
"""Basic command and message handlers."""

import datetime
from telebot import types
from db import get_active_subscriptions
from utils.keyboards import get_main_menu_keyboard
from utils.text_utils import strip_html
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
        try:
            if welcome_image_url:
                local_path = get_local_image_path(welcome_image_url)
                if local_path:
                    try:
                        with open(local_path, "rb") as photo:
                            bot.send_photo(user_id, photo, caption=WELCOME_MSG, reply_markup=keyboard)
                    except Exception as e:
                        log_warning("basic_handlers", f"send_photo local welcome image failed: {e}")
                        # Fallback to URL if local file send fails
                        bot.send_photo(user_id, welcome_image_url, caption=WELCOME_MSG, reply_markup=keyboard)
                else:
                    # Fallback to sending by URL if cache/download failed
                    bot.send_photo(user_id, welcome_image_url, caption=WELCOME_MSG, reply_markup=keyboard)
            else:
                bot.send_message(user_id, WELCOME_MSG, reply_markup=keyboard)
        except Exception as e:
            log_warning("basic_handlers", f"send_photo welcome failed, fallback to text: {e}")
            bot.send_message(user_id, WELCOME_MSG, reply_markup=keyboard)

    @bot.message_handler(func=lambda m: m.text == "Активные подписки")
    def handle_active(message: types.Message):
        user_id = message.from_user.id
        subs = get_active_subscriptions(user_id)
        subs = list(subs) if subs else []
        if not subs:
            bot.send_message(user_id, "У вас нет активных подписок.")
            return
        text = "Ваши активные подписки:\n"
        for s in subs:
            course_name = s["course_name"]
            clean_course_name = strip_html(course_name) if course_name else "Курс"
            channel_id = s["channel_id"]
            expiry_ts = s["expiry"]
            dt = datetime.datetime.fromtimestamp(expiry_ts)
            dstr = dt.strftime("%Y-%m-%d")
            text += f"• {clean_course_name} (доступ до {dstr}) – "
            if str(channel_id).startswith("@"):
                text += f"{channel_id}\n"
            else:
                text += "ссылка недоступна\n"
        bot.send_message(user_id, text, disable_web_page_preview=True)

    @bot.message_handler(func=lambda m: m.text == "Поддержка")
    def handle_support(message: types.Message):
        user_id = message.from_user.id
        bot.send_message(user_id, SUPPORT_MSG)

    @bot.message_handler(func=lambda m: m.text == "Оферта")
    def handle_oferta(message: types.Message):
        user_id = message.from_user.id
        oferta_url = "https://github.com/george-dvoryak/cdn/blob/main/oferta.pdf?raw=true"
        try:
            bot.send_document(user_id, oferta_url, caption="Договор оферты (PDF)")
        except Exception:
            # Fallback: send link if Telegram couldn't download the file
            bot.send_message(user_id, f"Договор оферты: {oferta_url}", disable_web_page_preview=False)

