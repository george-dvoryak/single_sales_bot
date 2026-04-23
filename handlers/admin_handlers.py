# handlers/admin_handlers.py
"""Admin-only command handlers."""

import sqlite3
import time
import datetime
import threading
from telebot import types
from db import get_all_active_subscriptions, get_expired_subscriptions, mark_subscription_expired, get_connection
from utils.text_utils import strip_html
from utils.channel import remove_user_from_channel, check_course_channels
from google_sheets import get_courses_data
from utils.logger import log_error, log_warning, log_info
from config import ADMIN_IDS, DATABASE_PATH, GSHEET_ID

# --- Broadcast state management ---
# Keyed by admin user_id. Two steps:
#   {'step': 'awaiting_text'}
#   {'step': 'awaiting_confirm', 'text': str, 'recipients': list[int]}
_broadcast_states: dict = {}

# admin_ids currently running a broadcast (prevents duplicate sends)
_active_broadcasts: set = set()


def _get_prodamus_recipients() -> list:
    """Return deduplicated list of user_ids from prodamus_payments."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT user_id FROM prodamus_payments WHERE user_id IS NOT NULL"
        )
        rows = cur.fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _do_broadcast(bot, admin_id: int, text: str, recipients: list) -> None:
    """Send broadcast messages in a daemon thread with per-message timeout and rate limiting."""
    sent = 0
    failed = 0
    total = len(recipients)
    try:
        for uid in recipients:
            try:
                bot.send_message(
                    uid,
                    text,
                    disable_web_page_preview=True,
                    timeout=10,
                )
                sent += 1
            except Exception as e:
                failed += 1
                if failed <= 5:
                    log_warning(
                        "admin_handlers",
                        f"Broadcast: failed to send to user {uid}: {e}",
                    )
            time.sleep(0.05)  # ~20 msg/sec to stay within Telegram rate limits
    except Exception as e:
        log_error("admin_handlers", f"Broadcast loop crashed unexpectedly: {e}")
    finally:
        _active_broadcasts.discard(admin_id)

    status = (
        f"✅ Рассылка завершена.\n"
        f"Отправлено: {sent} из {total}\n"
        f"Не доставлено: {failed}"
    )
    try:
        bot.send_message(admin_id, status)
    except Exception as e:
        log_error("admin_handlers", f"Broadcast: could not send status to admin {admin_id}: {e}")


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
        
        try:
            now = int(time.time())
            
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > 0 AND expiry <= ?", (now,))
            expired_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > ?", (now,))
            active_count = cur.fetchone()[0]
            
            report = f"📊 Статистика:\n"
            report += f"• Просроченных (необработанных): {expired_count}\n"
            report += f"• Активных: {active_count}\n\n"
            
            if expired_count == 0:
                bot.reply_to(message, report + "✅ Просроченных подписок не найдено.")
                return
            
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
            
            report += f"✅ Обработано: {processed}\n"
            if failed > 0:
                report += f"⚠️ Ошибок: {failed}"
            
            bot.reply_to(message, report)
            
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка при очистке: {e}")
            import traceback
            log_error("admin_handlers", f"Cleanup error: {traceback.format_exc()}")

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
                # users table was removed; gather all known user_ids from both payment tables
                cur.execute(
                    "SELECT DISTINCT user_id FROM prodamus_payments WHERE user_id IS NOT NULL "
                    "UNION SELECT DISTINCT user_id FROM purchases WHERE user_id IS NOT NULL;"
                )
            elif cmd == "/broadcast_buyers":
                cur.execute("SELECT DISTINCT user_id FROM purchases WHERE user_id IS NOT NULL;")
            elif cmd == "/broadcast_nonbuyers":
                # users who initiated a Prodamus payment but have no completed purchase
                cur.execute(
                    "SELECT DISTINCT user_id FROM prodamus_payments "
                    "WHERE user_id IS NOT NULL "
                    "AND user_id NOT IN (SELECT DISTINCT user_id FROM purchases WHERE user_id IS NOT NULL);"
                )
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

    # ------------------------------------------------------------------ #
    #  Button-based broadcast flow (3 steps)                             #
    # ------------------------------------------------------------------ #

    @bot.message_handler(func=lambda m: m.text == "📢 Рассылка")
    def handle_broadcast_button(message: types.Message):
        """Step 1 — admin presses the Broadcast button."""
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            bot.send_message(user_id, "У вас нет доступа к этой функции.")
            return

        if user_id in _active_broadcasts:
            bot.send_message(
                user_id,
                "⚠️ Рассылка уже выполняется. Дождитесь её завершения.",
            )
            return

        _broadcast_states[user_id] = {"step": "awaiting_text"}
        bot.send_message(
            user_id,
            "✏️ Введите текст рассылки.\n\nДля отмены напишите /cancel_broadcast.",
        )

    @bot.message_handler(commands=["cancel_broadcast"])
    def handle_cancel_broadcast_command(message: types.Message):
        """Cancel broadcast at any step via command."""
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            return
        _broadcast_states.pop(user_id, None)
        bot.send_message(user_id, "❌ Рассылка отменена.")

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id in ADMIN_IDS
            and m.from_user.id in _broadcast_states
            and _broadcast_states.get(m.from_user.id, {}).get("step") == "awaiting_text"
        )
    )
    def handle_broadcast_text_input(message: types.Message):
        """Step 2 — admin has typed the broadcast text; show confirmation."""
        user_id = message.from_user.id

        broadcast_text = message.text.strip()
        if not broadcast_text:
            bot.send_message(user_id, "Текст не может быть пустым. Попробуйте ещё раз.")
            return

        try:
            recipients = _get_prodamus_recipients()
        except Exception as e:
            log_error("admin_handlers", f"Broadcast: DB error fetching recipients: {e}")
            _broadcast_states.pop(user_id, None)
            bot.send_message(user_id, f"❌ Ошибка при получении списка получателей: {e}")
            return

        count = len(recipients)
        if count == 0:
            _broadcast_states.pop(user_id, None)
            bot.send_message(
                user_id,
                "⚠️ В таблице prodamus_payments нет пользователей. Рассылка отменена.",
            )
            return

        _broadcast_states[user_id] = {
            "step": "awaiting_confirm",
            "text": broadcast_text,
            "recipients": recipients,
        }

        preview = broadcast_text if len(broadcast_text) <= 300 else broadcast_text[:300] + "…"
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(
            types.InlineKeyboardButton(
                "✅ Отправить",
                callback_data=f"broadcast_confirm_{user_id}",
            ),
            types.InlineKeyboardButton(
                "❌ Отмена",
                callback_data=f"broadcast_cancel_{user_id}",
            ),
        )
        bot.send_message(
            user_id,
            f"📢 <b>Подтверждение рассылки</b>\n\n"
            f"Получателей: <b>{count}</b>\n\n"
            f"Текст:\n{preview}",
            parse_mode="HTML",
            reply_markup=confirm_markup,
        )

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("broadcast_confirm_")
        or call.data.startswith("broadcast_cancel_")
    )
    def handle_broadcast_confirm(call: types.CallbackQuery):
        """Step 3 — admin confirms or cancels the broadcast."""
        caller_id = call.from_user.id

        # Parse the admin_id embedded in callback_data to prevent IDOR
        parts = call.data.rsplit("_", 1)
        try:
            owner_id = int(parts[-1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Некорректный запрос.")
            return

        # Only the admin who initiated the broadcast may confirm/cancel it
        if caller_id not in ADMIN_IDS or caller_id != owner_id:
            bot.answer_callback_query(call.id, "У вас нет доступа.", show_alert=True)
            return

        action = "confirm" if call.data.startswith("broadcast_confirm_") else "cancel"

        if action == "cancel":
            _broadcast_states.pop(owner_id, None)
            bot.answer_callback_query(call.id, "Рассылка отменена.")
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id, call.message.message_id, reply_markup=None
                )
                bot.send_message(owner_id, "❌ Рассылка отменена.")
            except Exception:
                pass
            return

        # Confirm path
        state = _broadcast_states.get(owner_id)
        if not state or state.get("step") != "awaiting_confirm":
            bot.answer_callback_query(call.id, "Нет активного запроса на рассылку.")
            return

        if owner_id in _active_broadcasts:
            bot.answer_callback_query(call.id, "Рассылка уже выполняется.", show_alert=True)
            return

        broadcast_text = state["text"]
        recipients = state["recipients"]
        _broadcast_states.pop(owner_id, None)
        _active_broadcasts.add(owner_id)

        bot.answer_callback_query(call.id)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None
            )
        except Exception:
            pass
        bot.send_message(
            owner_id,
            f"🚀 Рассылка запущена. Получателей: {len(recipients)}.\nРезультат придёт по завершении.",
        )

        t = threading.Thread(
            target=_do_broadcast,
            args=(bot, owner_id, broadcast_text, recipients),
            daemon=True,
        )
        t.start()

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

