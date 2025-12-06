# handlers/admin_handlers.py
"""Admin-only command handlers."""

import sqlite3
import time
import datetime
from telebot import types
from db import get_all_active_subscriptions, get_expired_subscriptions, mark_subscription_expired, get_connection
from utils.text_utils import strip_html
from utils.channel import remove_user_from_channel, check_course_channels
from google_sheets import get_courses_data
from utils.logger import log_error, log_warning, log_info
from config import ADMIN_IDS, DATABASE_PATH, GSHEET_ID


def cleanup_expired_subscriptions(bot, notify_admins: bool = True):
    """
    Clean up expired subscriptions by removing users from channels.
    
    Args:
        bot: Telegram bot instance
        notify_admins: If True, send notification to admins about the cleanup results
        
    Returns:
        dict: Statistics about the cleanup process with keys:
            - expired_count: Number of expired subscriptions found
            - active_count: Number of active subscriptions
            - processed: Number of subscriptions successfully processed
            - failed: Number of subscriptions that failed to process
            - success: Boolean indicating if cleanup completed without errors
    """
    result = {
        "expired_count": 0,
        "active_count": 0,
        "processed": 0,
        "failed": 0,
        "success": False
    }
    
    try:
        now = int(time.time())
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > 0 AND expiry <= ?", (now,))
        expired_count = cur.fetchone()[0]
        result["expired_count"] = expired_count
        
        cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > ?", (now,))
        active_count = cur.fetchone()[0]
        result["active_count"] = active_count
        
        if expired_count == 0:
            result["success"] = True
            if notify_admins:
                report = f"📊 Статистика:\n• Просроченных (необработанных): {expired_count}\n• Активных: {active_count}\n\n✅ Просроченных подписок не найдено."
                for aid in ADMIN_IDS:
                    try:
                        bot.send_message(aid, report)
                    except Exception:
                        pass
            return result
        
        # Process expired subscriptions
        expired = get_expired_subscriptions()
        processed = 0
        failed = 0
        
        for rec in expired:
            try:
                user_id = rec["user_id"]
                course_id = rec["course_id"]
                course_name = rec["course_name"]
                channel_id = rec["channel_id"]
                
                if channel_id:
                    ok = remove_user_from_channel(bot, user_id, channel_id)
                    if not ok:
                        # Double check
                        try:
                            member = bot.get_chat_member(channel_id, user_id)
                            status = getattr(member, "status", "unknown")
                            if status in ("left", "kicked"):
                                ok = True
                        except:
                            ok = True  # Assume removed if can't check
                
                mark_subscription_expired(user_id, course_id)
                
                # Try to notify user
                try:
                    clean_course_name = strip_html(course_name) if course_name else "курсу"
                    bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
                except:
                    pass
                
                processed += 1
            except Exception as e:
                failed += 1
                log_error("admin_handlers", f"Error processing expired subscription: {e}")
        
        result["processed"] = processed
        result["failed"] = failed
        result["success"] = True
        
        if notify_admins:
            report = f"📊 Статистика:\n"
            report += f"• Просроченных (необработанных): {expired_count}\n"
            report += f"• Активных: {active_count}\n\n"
            report += f"✅ Обработано: {processed}\n"
            if failed > 0:
                report += f"⚠️ Ошибок: {failed}"
            
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, report)
                except Exception:
                    pass
        
        return result
        
    except Exception as e:
        log_error("admin_handlers", f"Cleanup error: {e}", exc_info=True)
        result["success"] = False
        if notify_admins:
            error_msg = f"❌ Ошибка при очистке: {e}"
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, error_msg)
                except Exception:
                    pass
        return result


def register_handlers(bot):
    """Register admin handlers"""
    
    @bot.message_handler(func=lambda m: m.text == "📊 Все подписки")
    def handle_admin_all_subscriptions(message: types.Message):
        """Admin handler: show all active subscriptions for all users"""
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            bot.send_message(user_id, "У вас нет доступа к этой функции.")
            return
        
        try:
            all_subs = get_all_active_subscriptions()
            all_subs = list(all_subs) if all_subs else []
            
            if not all_subs:
                bot.send_message(user_id, "Нет активных подписок.")
                return
            
            # Group by user for better readability
            user_subs = {}
            for s in all_subs:
                uid = s["user_id"]
                if uid not in user_subs:
                    user_subs[uid] = []
                user_subs[uid].append(s)
            
            text = f"📊 Все активные подписки ({len(all_subs)} всего):\n\n"
            
            for uid, subs in sorted(user_subs.items()):
                text += f"👤 ID {uid}:\n"
                
                for s in subs:
                    course_name = s["course_name"]
                    clean_course_name = strip_html(course_name) if course_name else "Курс"
                    expiry_ts = s["expiry"]
                    dt = datetime.datetime.fromtimestamp(expiry_ts)
                    dstr = dt.strftime("%Y-%m-%d %H:%M")
                    text += f"  • {clean_course_name}\n    Доступ до {dstr}\n"
                text += "\n"
            
            # Split message if too long (Telegram limit is 4096 chars)
            if len(text) > 4000:
                parts = text.split("\n\n")
                current_msg = ""
                for part in parts:
                    if len(current_msg) + len(part) + 2 > 4000:
                        bot.send_message(user_id, current_msg, disable_web_page_preview=True)
                        current_msg = part + "\n\n"
                    else:
                        current_msg += part + "\n\n"
                if current_msg.strip():
                    bot.send_message(user_id, current_msg, disable_web_page_preview=True)
            else:
                bot.send_message(user_id, text, disable_web_page_preview=True)
                
        except Exception as e:
            log_error("admin_handlers", f"Error in handle_admin_all_subscriptions: {e}")
            bot.send_message(user_id, f"Ошибка при получении подписок: {e}")

    @bot.message_handler(func=lambda m: m.text == "📋 Google Sheets")
    def handle_admin_google_sheets(message: types.Message):
        """Admin handler: open Google Sheets link"""
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            bot.send_message(user_id, "У вас нет доступа к этой функции.")
            return
        
        if not GSHEET_ID:
            bot.send_message(user_id, "Google Sheets ID не настроен.")
            return
        
        sheets_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit"
        
        # Create inline keyboard with URL button
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("📋 Открыть Google Sheets", url=sheets_url))
        
        bot.send_message(
            user_id,
            "Нажмите на кнопку ниже, чтобы открыть Google Sheets:",
            reply_markup=keyboard
        )

    @bot.message_handler(commands=['cleanup_expired'])
    def handle_cleanup_expired(message: types.Message):
        """Admin command to manually trigger expired subscriptions cleanup"""
        if message.from_user.id not in ADMIN_IDS:
            return
        
        bot.reply_to(message, "🔄 Запуск очистки просроченных подписок...")
        
        # Use the shared cleanup function
        result = cleanup_expired_subscriptions(bot, notify_admins=False)
        
        if not result["success"]:
            bot.reply_to(message, f"❌ Ошибка при очистке. Проверьте логи.")
            return
        
        # Build report for the admin who triggered the command
        report = f"📊 Статистика:\n"
        report += f"• Просроченных (необработанных): {result['expired_count']}\n"
        report += f"• Активных: {result['active_count']}\n\n"
        
        if result["expired_count"] == 0:
            bot.reply_to(message, report + "✅ Просроченных подписок не найдено.")
        else:
            report += f"✅ Обработано: {result['processed']}\n"
            if result["failed"] > 0:
                report += f"⚠️ Ошибок: {result['failed']}"
            bot.reply_to(message, report)

    @bot.message_handler(commands=['broadcast_all', 'broadcast_buyers', 'broadcast_nonbuyers'])
    def handle_broadcast(message: types.Message):
        if message.from_user.id not in ADMIN_IDS:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "После команды укажите текст сообщения.")
            return
        cmd = parts[0]
        text = parts[1]

        recipients = []
        try:
            # Use separate connection for broadcast to avoid conflicts
            conn = sqlite3.connect(DATABASE_PATH)
            cur = conn.cursor()
            if cmd == "/broadcast_all":
                cur.execute("SELECT user_id FROM users;")
            elif cmd == "/broadcast_buyers":
                cur.execute("SELECT DISTINCT user_id FROM purchases;")
            elif cmd == "/broadcast_nonbuyers":
                cur.execute("SELECT user_id FROM users WHERE user_id NOT IN (SELECT DISTINCT user_id FROM purchases);")
            rows = cur.fetchall()
            recipients = [r[0] for r in rows]
            conn.close()
        except Exception as e:
            log_error("admin_handlers", f"Broadcast database error: {e}")
            bot.reply_to(message, f"Ошибка при получении списка получателей: {e}")
            return

        sent = 0
        failed = 0
        for uid in recipients:
            try:
                bot.send_message(uid, text, disable_web_page_preview=True)
                sent += 1
            except Exception as e:
                failed += 1
                # Log first few failures for debugging
                if failed <= 3:
                    log_warning("admin_handlers", f"Failed to send broadcast to user {uid}: {e}")
        total = len(recipients)
        reply_msg = f"Отправлено {sent} из {total} пользователям."
        if failed > 0:
            reply_msg += f" Не удалось отправить: {failed}."
        bot.reply_to(message, reply_msg)

    @bot.message_handler(commands=["diag_channels"])
    def handle_diag_channels(message: types.Message):
        if message.from_user.id not in ADMIN_IDS:
            return
        report = check_course_channels(bot, get_courses_data)
        # Split long responses
        parts = []
        current = ""
        for line in report.split("\n"):
            if len(current) + len(line) + 1 > 3900:
                parts.append(current)
                current = ""
            current += (("\n" if current else "") + line)
        if current:
            parts.append(current)
        for p in parts:
            try:
                bot.send_message(message.chat.id, "🔎 Диагностика каналов:\n" + p, disable_web_page_preview=True)
            except Exception:
                pass

