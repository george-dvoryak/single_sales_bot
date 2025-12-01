# utils/channel.py
"""Channel management utilities."""

import datetime


def remove_user_from_channel(bot, user_id: int, channel_id: str) -> bool:
    """
    Remove user from channel by banning and immediately unbanning.
    This effectively removes the user from the channel.
    """
    timestamp = datetime.datetime.now().isoformat()
    
    if not channel_id:
        print(f"[{timestamp}] [remove_user_from_channel] ERROR: No channel_id provided for user {user_id}")
        return False
    
    print(f"[{timestamp}] [remove_user_from_channel] Starting removal process: user_id={user_id}, channel_id={channel_id}")
    
    # First, check if user is actually a member before attempting removal
    try:
        print(f"[{timestamp}] [remove_user_from_channel] Checking user membership status...")
        member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        member_status = getattr(member, "status", "unknown")
        print(f"[{timestamp}] [remove_user_from_channel] User {user_id} current status in channel {channel_id}: {member_status}")
        
        if member_status in ("left", "kicked"):
            print(f"[{timestamp}] [remove_user_from_channel] User {user_id} already not a member (status: {member_status}), skipping removal")
            return True
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[{timestamp}] [remove_user_from_channel] Warning: Could not check membership status: {e}")
        # Continue with removal attempt anyway
    
    try:
        print(f"[{timestamp}] [remove_user_from_channel] Attempting to ban user {user_id} from channel {channel_id}...")
        # First, try to ban the user (removes them from channel)
        bot.ban_chat_member(chat_id=channel_id, user_id=user_id, until_date=None)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully banned user {user_id}")
        
        # Then immediately unban (allows them to rejoin if needed, but they're already removed)
        print(f"[{timestamp}] [remove_user_from_channel] Unbanning user {user_id}...")
        bot.unban_chat_member(chat_id=channel_id, user_id=user_id, only_if_banned=True)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully unbanned user {user_id}")
        
        # Verify removal by checking status again
        try:
            member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            final_status = getattr(member, "status", "unknown")
            print(f"[{timestamp}] [remove_user_from_channel] Verification: User {user_id} final status: {final_status}")
            if final_status in ("left", "kicked"):
                print(f"[{timestamp}] [remove_user_from_channel] ✅ SUCCESS: User {user_id} successfully removed from channel {channel_id}")
                return True
            else:
                print(f"[{timestamp}] [remove_user_from_channel] ⚠️ WARNING: User {user_id} still has status '{final_status}' after ban/unban")
                return True  # Still return True as ban/unban succeeded
        except Exception as verify_e:
            print(f"[{timestamp}] [remove_user_from_channel] Could not verify removal status: {verify_e}")
            # If we can't verify but ban/unban succeeded, assume success
            print(f"[{timestamp}] [remove_user_from_channel] ✅ SUCCESS: Ban/unban completed, assuming removal successful")
            return True
            
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[{timestamp}] [remove_user_from_channel] ERROR during ban/unban: {e}")
        print(f"[{timestamp}] [remove_user_from_channel] Error type: {type(e).__name__}")
        
        # Check if user is already not a member
        if any(s in error_msg for s in ("user not found", "user is not a member", "chat not found")):
            print(f"[{timestamp}] [remove_user_from_channel] User {user_id} already not a member of {channel_id} (error indicates this)")
            return True
        
        # Check if bot doesn't have admin rights
        if any(s in error_msg for s in ("not enough rights", "not an admin", "can't ban", "can't restrict")):
            print(f"[{timestamp}] [remove_user_from_channel] ❌ FAILED: Bot doesn't have admin rights in {channel_id}: {e}")
            return False
        
        print(f"[{timestamp}] [remove_user_from_channel] ❌ FAILED: Unknown error removing {user_id} from {channel_id}: {e}")
        return False


def check_course_channels(bot, get_courses_data) -> str:
    """
    Check channel configuration and bot permissions.
    Returns human-readable report.
    """
    from utils.text_utils import strip_html
    
    lines = []
    # Get bot info
    try:
        me = bot.get_me()
        bot_id = me.id
        bot_name = f"@{me.username}" if getattr(me, "username", None) else str(me.id)
    except Exception as e:
        bot_id = None
        bot_name = "<unknown>"
        lines.append(f"⚠️ Не удалось получить информацию о боте: {e}")

    # Get courses
    try:
        courses = get_courses_data()
    except Exception as e:
        return f"❌ Не удалось получить список курсов: {e}"

    if not courses:
        return "Список курсов пуст."

    for course in courses:
        name = course.get("name", "Курс")
        channel = str(course.get("channel", "") or "")
        if not channel:
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name}: канал не указан.")
            continue

        # Check chat availability
        try:
            chat = bot.get_chat(channel)
        except Exception as e:
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name} — {channel}: ❌ чат недоступен для бота (возможно, бот не добавлен/не админ, или неверный ID). Ошибка: {e}")
            continue

        if channel.startswith("@"):
            # Public channel - use direct link
            public_url = f"https://t.me/{channel[1:]}"
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name} — {channel}: ✅ публичный канал, ссылка ок: {public_url}")
        else:
            # Private/numeric ID - check bot admin status
            try:
                admins = bot.get_chat_administrators(chat.id)
            except Exception as e:
                clean_name = strip_html(name) if name else "Курс"
                lines.append(f"• {clean_name} — {channel}: ⚠️ не удалось получить админов. Ошибка: {e}")
                continue

            bot_admin = None
            for a in admins:
                try:
                    if a.user.id == bot_id:
                        bot_admin = a
                        break
                except Exception:
                    pass

            if not bot_admin:
                clean_name = strip_html(name) if name else "Курс"
                lines.append(f"• {clean_name} — {channel}: ❌ бот {bot_name} не является админом. Добавьте бота админом канала.")
            else:
                can_invite = getattr(bot_admin, "can_invite_users", False)
                can_manage = getattr(bot_admin, "can_manage_chat", False)
                if can_invite or can_manage:
                    clean_name = strip_html(name) if name else "Курс"
                    lines.append(f"• {clean_name} — {channel}: ✅ бот админ, права на приглашения есть.")
                else:
                    clean_name = strip_html(name) if name else "Курс"
                    lines.append(f"• {clean_name} — {channel}: ⚠️ бот админ, но нет права приглашать пользователей. Включите право «Добавлять пользователей».")

    return "\n".join(lines)

