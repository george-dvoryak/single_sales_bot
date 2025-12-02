# Bot Not Responding - Troubleshooting Guide

If your bot is not replying to messages, follow these steps:

## Step 1: Check Webhook Status

Visit this URL in your browser:
```
https://ysingle-goshadvoryak.pythonanywhere.com/webhook_info
```

This will show you:
- Current webhook URL configured in Telegram
- Pending update count
- Last error message (if any)
- Your configured webhook route

**What to look for:**
- `webhook_url` should match your PythonAnywhere domain
- `pending_update_count` should be 0 (if it's high, there are unprocessed updates)
- `last_error_message` should be empty/null
- `configured_route` should match the webhook URL path

## Step 2: Check PythonAnywhere Error Log

1. Go to PythonAnywhere **Web** tab
2. Click **"Error log"**
3. Look for lines starting with `[webhook]`
4. Check if you see:
   - `[webhook] Received POST request` - means Telegram is sending updates
   - `[webhook] Processing update` - means update is being processed
   - `[webhook] ERROR` - means something went wrong

**Common errors:**
- `ERROR: No data` - Telegram isn't sending data correctly
- `ERROR: Invalid update` - Update parsing failed
- `ERROR processing update` - Handler failed

## Step 3: Verify Webhook is Set

The webhook should be automatically set when the app starts. Check the error log for:
```
Webhook set to https://ysingle-goshadvoryak.pythonanywhere.com/...
```

If you don't see this, the webhook wasn't set. Check:
1. `.env` file has `USE_WEBHOOK=True`
2. `.env` file has `WEBHOOK_HOST=ysingle-goshadvoryak.pythonanywhere.com`
3. `.env` file has `WEBHOOK_SECRET_TOKEN=your_secret_token`

## Step 4: Manually Set Webhook (if needed)

If the webhook wasn't set automatically, you can set it manually:

1. Open PythonAnywhere **Bash** console
2. Run:
```bash
cd ~/single_sales_bot
python3 -c "
import sys
sys.path.insert(0, '.')
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET_TOKEN
import telebot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
bot.remove_webhook()
import time
time.sleep(1)
bot.set_webhook(
    url=WEBHOOK_URL,
    secret_token=WEBHOOK_SECRET_TOKEN,
    drop_pending_updates=True
)
print(f'Webhook set to: {WEBHOOK_URL}')
info = bot.get_webhook_info()
print(f'Webhook info: {info.url}, pending: {info.pending_update_count}')
"
```

## Step 5: Test the Webhook Endpoint

Send a test message to your bot, then immediately check:

1. **Error log** - Should show `[webhook] Received POST request`
2. **Webhook info** - Visit `/webhook_info` to see if pending updates increased

If you see `[webhook] Received POST request` but the bot doesn't reply:
- Check for `[webhook] ERROR` messages
- The handler might be failing silently

## Step 6: Check Handler Registration

The error log should show:
```
[main.py] Starting handler registration
[main.py] All handlers registered successfully
```

If you see `ERROR registering handlers`, the handlers aren't registered and the bot won't respond.

## Step 7: Test with a Simple Message

Try sending `/start` to your bot. This should trigger the basic handler.

Check the error log for:
- `[webhook] Processing update: update_id=...`
- Any error messages after that

## Step 8: Common Issues and Fixes

### Issue: Webhook URL doesn't match
**Symptom:** `webhook_info` shows different URL than configured  
**Fix:** 
1. Check `.env` file `WEBHOOK_HOST` matches your domain
2. Reload web app
3. Or manually set webhook (Step 4)

### Issue: Pending updates count is high
**Symptom:** `pending_update_count` > 0  
**Fix:** 
1. The webhook might have been down
2. Reload web app to process pending updates
3. Or manually set webhook with `drop_pending_updates=True`

### Issue: "ERROR: No data" in logs
**Symptom:** Webhook receives request but no data  
**Fix:** 
1. Check if webhook route is correct
2. Verify Telegram is sending to correct URL
3. Check webhook secret token matches

### Issue: "ERROR processing update"
**Symptom:** Update received but handler fails  
**Fix:** 
1. Check the full error traceback in error log
2. Usually means a handler function has a bug
3. Check if all dependencies are installed

### Issue: No `[webhook]` messages in log
**Symptom:** Bot doesn't respond and no webhook logs  
**Fix:** 
1. Webhook might not be set in Telegram
2. Check `/webhook_info` to see current webhook URL
3. Manually set webhook (Step 4)

## Step 9: Enable More Logging

If you need more detailed logging, the webhook endpoint now logs:
- When a request is received
- The data received (first 200 chars)
- When processing starts
- When processing completes
- Any errors

All logs appear in PythonAnywhere **Error log**.

## Step 10: Reset Everything

If nothing works, try a complete reset:

1. **Remove webhook:**
```bash
cd ~/single_sales_bot
python3 -c "
import sys
sys.path.insert(0, '.')
from config import TELEGRAM_BOT_TOKEN
import telebot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
bot.remove_webhook()
print('Webhook removed')
"
```

2. **Reload web app** in PythonAnywhere

3. **Check error log** - webhook should be set automatically

4. **Send test message** to bot

5. **Check error log** for `[webhook]` messages

## Quick Diagnostic Commands

**Check webhook status:**
```bash
cd ~/single_sales_bot
python3 -c "
import sys
sys.path.insert(0, '.')
from config import TELEGRAM_BOT_TOKEN
import telebot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
info = bot.get_webhook_info()
print(f'URL: {info.url}')
print(f'Pending: {info.pending_update_count}')
print(f'Last error: {info.last_error_message}')
"
```

**Test webhook endpoint manually:**
Visit: `https://ysingle-goshadvoryak.pythonanywhere.com/webhook_info`

**Check if handlers are registered:**
Look for `[main.py] All handlers registered successfully` in error log

## Still Not Working?

1. **Copy the full error log** (last 100 lines)
2. **Check `/webhook_info` endpoint** - screenshot the output
3. **Verify `.env` file** has all required values
4. **Check that webhook route matches** - compare `configured_route` in `/webhook_info` with actual webhook URL

The most common issue is that the webhook URL in Telegram doesn't match your configured route. Always check `/webhook_info` first!


