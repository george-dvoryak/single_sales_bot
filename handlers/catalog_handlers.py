# handlers/catalog_handlers.py
"""Catalog and course viewing handlers."""

from telebot import types
from google_sheets import get_courses_data
from db import has_active_subscription
from utils.keyboards import create_catalog_keyboard, create_course_buttons
from utils.text_utils import strip_html, format_for_telegram_html
from utils.images import get_local_image_path
from utils.text_loader import get_text, get_texts
from utils.logger import log_error, log_warning, log_info

CATALOG_TITLE = get_text("catalog_title", "Каталог курсов:")
ALREADY_PURCHASED_MSG = get_text("already_purchased_message", "У вас уже есть доступ к этому курсу.")


def register_handlers(bot):
    """Register catalog handlers"""
    
    def send_catalog_message(user_id, edit_message=None, edit_message_id=None, edit_chat_id=None):
        """Helper function to send/update catalog message"""
        try:
            courses = get_courses_data()
        except Exception as e:
            error_msg = "Не удалось загрузить каталог курсов. Попробуйте позже."
            if edit_message:
                try:
                    bot.edit_message_text(error_msg, chat_id=edit_chat_id, message_id=edit_message_id)
                except Exception:
                    bot.send_message(user_id, error_msg)
            else:
                bot.send_message(user_id, error_msg)
            log_error("catalog_handlers", f"Error fetching courses: {e}")
            return
        
        if not courses:
            empty_msg = "Каталог пока пуст."
            if edit_message:
                try:
                    bot.edit_message_text(empty_msg, chat_id=edit_chat_id, message_id=edit_message_id)
                except Exception:
                    bot.send_message(user_id, empty_msg)
            else:
                bot.send_message(user_id, empty_msg)
            return

        kb = create_catalog_keyboard(courses)
        texts = get_texts()
        banner_url = texts.get("catalog_image_url")
        caption = format_for_telegram_html(texts.get("catalog_text", CATALOG_TITLE))
        
        if edit_message:
            # When going back to catalog, always delete old message and send new one
            # This ensures the image updates correctly (can't change photo in existing message)
            try:
                bot.delete_message(chat_id=edit_chat_id, message_id=edit_message_id)
            except Exception:
                pass  # If deletion fails (e.g., message too old), continue anyway
            # Send new catalog message
            try:
                if banner_url:
                    local_path = get_local_image_path(banner_url)
                    if local_path:
                    try:
                        with open(local_path, "rb") as photo:
                            bot.send_photo(user_id, photo, caption=caption, reply_markup=kb, parse_mode='HTML')
                        except Exception as e:
                            log_warning("catalog_handlers", f"send_photo local catalog banner failed: {e}")
                            bot.send_photo(user_id, banner_url, caption=caption, reply_markup=kb, parse_mode='HTML')
                    else:
                        bot.send_photo(user_id, banner_url, caption=caption, reply_markup=kb, parse_mode='HTML')
                else:
                    bot.send_message(user_id, caption, reply_markup=kb, parse_mode='HTML')
            except Exception as e:
                log_warning("catalog_handlers", f"send catalog banner failed, fallback to text: {e}")
                bot.send_message(user_id, caption, reply_markup=kb, parse_mode='HTML')
        else:
            # Send new message
            try:
                if banner_url:
                    local_path = get_local_image_path(banner_url)
                    if local_path:
                        try:
                            with open(local_path, "rb") as photo:
                                bot.send_photo(user_id, photo, caption=caption, reply_markup=kb, parse_mode='HTML')
                        except Exception as e:
                            log_warning("catalog_handlers", f"send_photo local catalog banner (no-edit) failed: {e}")
                            bot.send_photo(user_id, banner_url, caption=caption, reply_markup=kb, parse_mode='HTML')
                    else:
                        bot.send_photo(user_id, banner_url, caption=caption, reply_markup=kb, parse_mode='HTML')
                else:
                    bot.send_message(user_id, caption, reply_markup=kb, parse_mode='HTML')
            except Exception as e:
                log_warning("catalog_handlers", f"send catalog banner (no-edit) failed, fallback to text: {e}")
                bot.send_message(user_id, caption, reply_markup=kb, parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.text == "Каталог")
    def handle_catalog(message: types.Message):
        user_id = message.from_user.id
        send_catalog_message(user_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("course_"))
    def cb_course(c: types.CallbackQuery):
        user_id = c.from_user.id
        course_id = c.data.split("_", 1)[1]
        
        try:
            courses = get_courses_data()
        except Exception:
            bot.answer_callback_query(c.id, "Ошибка загрузки курса.", show_alert=True)
            return
        course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
        if not course:
            bot.answer_callback_query(c.id, "Курс не найден.", show_alert=True)
            return

        name = course.get("name", "")
        desc = course.get("description", "")
        price = course.get("price", 0)
        duration_days = int(course.get("duration_days", 0) or 0)
        image_url = course.get("image_url", "")
        channel_id = course.get("channel", "")

        # Format course name with HTML support (bold, newlines)
        formatted_name = format_for_telegram_html(name) if name else "Курс"

        if has_active_subscription(user_id, str(course_id)):
            clean_desc = format_for_telegram_html(desc) if desc else ""
            text = f"{formatted_name}\n{clean_desc}\n\n✅ {ALREADY_PURCHASED_MSG}"
            ikb = types.InlineKeyboardMarkup()
            if channel_id:
                if str(channel_id).startswith("@"):
                    url = f"https://t.me/{channel_id[1:]}"
                    ikb.add(types.InlineKeyboardButton("Открыть канал курса", url=url))
                else:
                    invite_link = None
                    try:
                        invite = bot.create_chat_invite_link(chat_id=channel_id, member_limit=1, expire_date=None)
                        invite_link = invite.invite_link
                    except Exception as e:
                        log_error("catalog_handlers", f"Invite link error: {e}")
                    if invite_link:
                        ikb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
            ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
            try:
                if c.message.content_type == "photo":
                    bot.edit_message_caption(chat_id=c.message.chat.id, message_id=c.message.message_id, caption=text, reply_markup=ikb, parse_mode='HTML')
                else:
                    bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=ikb, parse_mode='HTML')
            except Exception:
                bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
            bot.answer_callback_query(c.id)
            return

        # Format description with HTML support (bold, newlines)
        clean_desc = format_for_telegram_html(desc) if desc else ""
        if duration_days > 0:
            access_text = f"Доступ: {duration_days} дн."
        else:
            access_text = "Доступ: без ограничения по времени"

        text = f"{formatted_name}\n{clean_desc}\n\nЦена: {price} руб.\n{access_text}"
        
        # Use the create_course_buttons function to get payment buttons
        ikb = create_course_buttons(course_id)
        
        # Try to edit existing message first, then fallback to sending new message
        message_sent = False
        try:
            if image_url:
                # If course has image, try to edit message media (if original was photo) or send new photo
                if c.message.content_type == "photo":
                    # Try to edit photo
                    try:
                        bot.edit_message_media(
                            chat_id=c.message.chat.id,
                            message_id=c.message.message_id,
                            media=types.InputMediaPhoto(image_url, caption=text, parse_mode='HTML'),
                            reply_markup=ikb
                        )
                        bot.answer_callback_query(c.id)
                        return
                    except Exception as e:
                        # If edit fails, delete old message and send new one
                        log_warning("catalog_handlers", f"Failed to edit message media: {e}")
                        try:
                            bot.delete_message(chat_id=c.message.chat.id, message_id=c.message.message_id)
                        except Exception:
                            pass
                # Send new photo (either because original wasn't photo, or edit/delete failed)
                local_path = get_local_image_path(image_url)
                if local_path:
                    try:
                        with open(local_path, "rb") as photo:
                            bot.send_photo(user_id, photo, caption=text, reply_markup=ikb, parse_mode='HTML')
                    except Exception as e:
                        log_warning("catalog_handlers", f"send_photo local course image failed: {e}")
                        bot.send_photo(user_id, image_url, caption=text, reply_markup=ikb, parse_mode='HTML')
                else:
                    bot.send_photo(user_id, image_url, caption=text, reply_markup=ikb, parse_mode='HTML')
                message_sent = True
            else:
                # No course image - edit text or send new message
                if c.message.content_type == "photo":
                    # Original was photo, but course has no image - send text message
                    bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
                    message_sent = True
                else:
                    # Original was text - can edit
                    try:
                        bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=ikb, parse_mode='HTML')
                        message_sent = True
                    except Exception as e:
                        log_warning("catalog_handlers", f"Failed to edit message text: {e}")
                        # If edit fails, send new message
                        bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
                        message_sent = True
            bot.answer_callback_query(c.id)
        except Exception as e:
            # Fallback: send text message if everything else fails (only if we haven't sent anything yet)
            log_error("catalog_handlers", f"Error in course handler: {e}")
            if not message_sent:
                bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
            bot.answer_callback_query(c.id)

    @bot.callback_query_handler(func=lambda c: c.data == "back_to_catalog")
    def cb_back_to_catalog(c: types.CallbackQuery):
        user_id = c.from_user.id
        send_catalog_message(
            user_id,
            edit_message=c.message,
            edit_message_id=c.message.message_id,
            edit_chat_id=c.message.chat.id
        )
        bot.answer_callback_query(c.id)

