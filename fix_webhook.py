#!/usr/bin/env python3
"""
Temporary script to fix webhook registration after security update.
Run this once to re-register the webhook with the new secure path.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET_TOKEN, USE_WEBHOOK
import telebot
import hashlib

if not USE_WEBHOOK:
    print("❌ USE_WEBHOOK is False. Set USE_WEBHOOK=True in .env file first.")
    sys.exit(1)

if not WEBHOOK_URL:
    print("❌ WEBHOOK_URL is not set. Check your .env file.")
    sys.exit(1)

# Calculate the new secure webhook path
token_hash = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).hexdigest()[:16]
new_path = f"/webhook_{token_hash}"
print(f"📋 New secure webhook path: {new_path}")

# Initialize bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Get current webhook info
print("\n🔍 Current webhook status:")
try:
    current_info = bot.get_webhook_info()
    print(f"  URL: {current_info.url}")
    print(f"  Pending updates: {current_info.pending_update_count}")
    if current_info.last_error_message:
        print(f"  Last error: {current_info.last_error_message}")
except Exception as e:
    print(f"  Error getting webhook info: {e}")

# Remove old webhook
print("\n🗑️  Removing old webhook...")
try:
    bot.remove_webhook()
    print("  ✅ Old webhook removed")
except Exception as e:
    print(f"  ⚠️  Error removing webhook: {e}")

# Set new webhook
print(f"\n🔧 Setting new webhook to: {WEBHOOK_URL}")
try:
    bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET_TOKEN if WEBHOOK_SECRET_TOKEN else None,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "pre_checkout_query"]
    )
    print("  ✅ Webhook set successfully!")
except Exception as e:
    print(f"  ❌ Error setting webhook: {e}")
    sys.exit(1)

# Verify new webhook
print("\n✅ Verifying new webhook...")
try:
    new_info = bot.get_webhook_info()
    print(f"  URL: {new_info.url}")
    print(f"  Pending updates: {new_info.pending_update_count}")
    if new_info.url == WEBHOOK_URL:
        print("  ✅ Webhook URL matches configuration!")
    else:
        print(f"  ⚠️  Webhook URL doesn't match! Expected: {WEBHOOK_URL}")
        print(f"     Got: {new_info.url}")
except Exception as e:
    print(f"  ❌ Error verifying webhook: {e}")

print("\n✨ Done! The bot should now receive updates.")
print(f"   Make sure your Flask app is listening on: {new_path}")

