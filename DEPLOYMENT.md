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
pip3.10 install --user -r requirements.txt
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

