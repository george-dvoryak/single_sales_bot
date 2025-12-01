# Deployment Guide

## Quick Deployment on PythonAnywhere

### 1. Upload Code

```bash
# On PythonAnywhere Bash console
cd ~
git clone <your-repo-url> single_sales_bot
cd single_sales_bot
```

### 2. Install Dependencies

```bash
pip3 install --user -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:

```bash
nano .env
```

Add your configuration:
```env
TELEGRAM_BOT_TOKEN=your_token_here
PAYMENT_PROVIDER_TOKEN=your_yookassa_token
CURRENCY=RUB
DATABASE_PATH=bot.db
GSHEET_ID=your_sheet_id
ADMIN_IDS=your_telegram_id
USE_WEBHOOK=True
WEBHOOK_HOST=yourusername.pythonanywhere.com
WEBHOOK_SECRET_TOKEN=generate_random_string_here

# Optional: Enable ProDAMUS as a second payment method
ENABLE_PRODAMUS=false
PRODAMUS_TEST_MODE=true
PRODAMUS_PAYFORM_URL=https://demo.payform.ru
PRODAMUS_SECRET_KEY=your_secret_key_here
```

### 4. Setup Web App

1. Go to Web tab in PythonAnywhere
2. Click "Add a new web app"
3. Choose "Manual configuration" and Python 3.10
4. Set Source code: `/home/yourusername/single_sales_bot`

### 5. Configure WSGI

Click on WSGI configuration file and replace contents with:

```python
import sys
import os

# Add your project directory to the sys.path
path = '/home/yourusername/single_sales_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Import the Flask application
from webhook_app import application
```

### 6. Reload Web App

Click "Reload" button on Web tab.

### 7. Verify

Visit: `https://yourusername.pythonanywhere.com/`  
You should see: "OK"

Visit: `https://yourusername.pythonanywhere.com/diag`  
You should see channel diagnostics.

## Running Locally

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file with:
```env
TELEGRAM_BOT_TOKEN=your_token_here
PAYMENT_PROVIDER_TOKEN=your_yookassa_token
CURRENCY=RUB
DATABASE_PATH=bot.db
GSHEET_ID=your_sheet_id
ADMIN_IDS=your_telegram_id
USE_WEBHOOK=False

# Optional: Enable ProDAMUS as a second payment method
ENABLE_PRODAMUS=false
PRODAMUS_TEST_MODE=true
PRODAMUS_PAYFORM_URL=https://demo.payform.ru
PRODAMUS_SECRET_KEY=your_secret_key_here
```

### 3. Run Bot

```bash
python main.py
```

The bot will start in polling mode.

## Troubleshooting

### Bot not responding
- Check that webhook is set correctly (visit `/diag` endpoint)
- Check logs in PythonAnywhere Error log
- Verify Telegram bot token is correct

### Payments not working
- Verify PAYMENT_PROVIDER_TOKEN is correct
- Check that YooKassa is properly configured in BotFather
- Test with small amounts first

### Channel access issues
- Run `/diag_channels` command as admin
- Make sure bot is admin in all channels
- Bot must have "Invite users" permission

## Updating Code

```bash
cd ~/single_sales_bot
git pull
# Reload web app in PythonAnywhere
```

## ProDAMUS Configuration (Optional)

If you want to enable ProDAMUS as a second payment method:

### 1. Set Environment Variables

In your `.env` file:
```env
ENABLE_PRODAMUS=true
PRODAMUS_TEST_MODE=true  # Set to false for production
PRODAMUS_PAYFORM_URL=https://yourshop.payform.ru
PRODAMUS_SECRET_KEY=your_secret_key_from_prodamus_dashboard
```

### 2. Configure Webhook in ProDAMUS Dashboard

Set the webhook URL in your ProDAMUS account settings:
```
https://yourusername.pythonanywhere.com/prodamus_webhook
```

### 3. How ProDAMUS Works

When a user selects ProDAMUS payment:
1. Bot asks for their email address
2. Bot generates a payment link and follows redirect to get short URL
3. User receives a short payment link like `https://demo.payform.ru/p/abc123`
4. After payment, ProDAMUS sends webhook notification to your server
5. Bot verifies webhook signature and grants/denies access based on payment status

### 4. Testing ProDAMUS Integration

1. Enable test mode: `PRODAMUS_TEST_MODE=true`
2. Use ProDAMUS test payment form URL
3. Make a test purchase through the bot
4. Check bot logs for webhook notifications
5. Verify that access is granted after successful payment

