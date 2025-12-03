# utils/keyboards.py
"""Keyboard builders for the bot."""

from telebot import types
from config import ADMIN_IDS


def get_main_menu_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    """Generate main menu keyboard, adding admin buttons if user is admin"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_catalog = types.KeyboardButton("Каталог")
    btn_subs = types.KeyboardButton("Активные подписки")
    btn_support = types.KeyboardButton("Поддержка")
    btn_oferta = types.KeyboardButton("Оферта")
    keyboard.add(btn_catalog)
    keyboard.add(btn_subs, btn_support)
    keyboard.add(btn_oferta)
    
    # Add admin buttons if user is admin
    if user_id in ADMIN_IDS:
        btn_admin_subs = types.KeyboardButton("📊 Все подписки")
        btn_admin_sheets = types.KeyboardButton("📋 Google Sheets")
        keyboard.add(btn_admin_subs, btn_admin_sheets)
    
    return keyboard


def create_course_buttons(course_id: str) -> types.InlineKeyboardMarkup:
    """Create payment buttons for a course (YooKassa and Prodamus)"""
    ikb = types.InlineKeyboardMarkup()
    ikb.add(types.InlineKeyboardButton("💳 Оплатить (ЮKassa)", callback_data=f"pay_yk_{course_id}"))
    ikb.add(types.InlineKeyboardButton("💳 Оплатить (Prodamus)", callback_data=f"pay_prodamus_{course_id}"))
    
    ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
    return ikb


def create_catalog_keyboard(courses: list) -> types.InlineKeyboardMarkup:
    """Create catalog keyboard with course buttons"""
    from utils.text_utils import strip_html
    
    kb = types.InlineKeyboardMarkup()
    for c in courses:
        cid = str(c.get("id"))
        name = c.get("name", "Курс")
        # Strip HTML from button labels (buttons don't support HTML formatting)
        button_label = strip_html(name)
        kb.add(types.InlineKeyboardButton(button_label, callback_data=f"course_{cid}"))
    return kb

