# Deployment Guide

## Complete PythonAnywhere Deployment (Step-by-Step)

### Step 1: Upload Your Code

**Option A: Using Git (Recommended)**
```bash
# Open a Bash console on PythonAnywhere
cd ~
git clone <your-repo-url> single_sales_bot
cd single_sales_bot
```

**Option B: Upload Files Manually**
1. Use PythonAnywhere Files tab
2. Create folder `/home/goshadvoryak/single_sales_bot/`
3. Upload all project files there

### Step 2: Install Dependencies

```bash
# In PythonAnywhere Bash console
cd ~/single_sales_bot
pip3 install --user -r requirements.txt
```

**Wait for installation to complete!** This may take 2-3 minutes.

### Step 3: Create and Configure .env File

```bash
cd ~/single_sales_bot
nano .env
```

**Copy and paste this, then replace with your actual values:**
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
PAYMENT_PROVIDER_TOKEN=your_yookassa_shop_id
CURRENCY=RUB
DATABASE_PATH=bot.db
GSHEET_ID=your_google_sheet_id
ADMIN_IDS=123456789
USE_WEBHOOK=True
WEBHOOK_HOST=ysingle-goshadvoryak.pythonanywhere.com
WEBHOOK_SECRET_TOKEN=my_secret_random_string_12345

# Optional: Enable ProDAMUS as a second payment method
ENABLE_PRODAMUS=false
PRODAMUS_TEST_MODE=true
PRODAMUS_PAYFORM_URL=https://demo.payform.ru
PRODAMUS_SECRET_KEY=your_secret_key_here
```

**Important Notes:**
- `TELEGRAM_BOT_TOKEN`: Get from BotFather
- `ADMIN_IDS`: Your Telegram user ID (not username)
- `WEBHOOK_SECRET_TOKEN`: Any random string for security
- `WEBHOOK_HOST`: Should match your PythonAnywhere domain

**Save the file:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 4: Create Web App

1. Go to **Web tab** in PythonAnywhere dashboard
2. Click **"Add a new web app"**
3. Click **"Next"** to confirm domain name
4. Select **"Manual configuration"**
5. Choose **Python 3.10** (or latest available)
6. Click **"Next"**

### Step 5: Configure Source Code Path

On the Web tab, find the **"Code"** section:
- Set **Source code** to: `/home/goshadvoryak/single_sales_bot`
- Set **Working directory** to: `/home/goshadvoryak/single_sales_bot`

### Step 6: Configure WSGI File (CRITICAL!)

1. On the Web tab, find **"Code"** section
2. Click on the WSGI configuration file link (it will say something like `/var/www/ysingle_goshadvoryak_pythonanywhere_com_wsgi.py`)
3. **DELETE ALL CONTENTS** of that file
4. **Replace with this EXACT code:**

```python
import sys
import os

# Add your project directory to the sys.path
path = '/home/goshadvoryak/single_sales_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Change to project directory
os.chdir(path)

# Import the Flask application
from webhook_app import application
```

5. Click **"Save"** at the top

### Step 7: Configure Virtual Environment (Optional but Recommended)

If you want to use a virtual environment:

```bash
cd ~/single_sales_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then in the Web tab, set **Virtualenv** to: `/home/goshadvoryak/single_sales_bot/venv`

### Step 8: Reload Web App

1. Go to **Web tab**
2. Scroll to the top
3. Click the big green **"Reload"** button
4. Wait for it to finish (shows success message)

### Step 9: Check Error Log

**If reload shows errors:**
1. Click on **"Error log"** link on Web tab
2. Read the last few lines to see what went wrong
3. Common issues and fixes below

### Step 10: Verify Deployment

**Test 1: Health Check**
Visit: `https://ysingle-goshadvoryak.pythonanywhere.com/`  
Expected: Page shows "OK"

**Test 2: Diagnostics**
Visit: `https://ysingle-goshadvoryak.pythonanywhere.com/diag`  
Expected: Shows channel diagnostics

**Test 3: Send Message to Bot**
Open Telegram and send `/start` to your bot  
Expected: Bot responds immediately

### Common Errors and Fixes

#### Error: "ModuleNotFoundError: No module named 'webhook_app'"

**Cause:** WSGI file can't find your code  
**Fix:**
1. Check that files exist at `/home/goshadvoryak/single_sales_bot/`
2. Make sure WSGI file has correct path (see Step 6)
3. Make sure `webhook_app.py` file exists in the directory
4. Check Error log for exact path that failed

#### Error: "ModuleNotFoundError: No module named 'telebot'"

**Cause:** Dependencies not installed  
**Fix:**
```bash
cd ~/single_sales_bot
pip3 install --user -r requirements.txt
# Then reload web app
```

#### Error: "No module named 'dotenv'"

**Cause:** python-dotenv not installed  
**Fix:**
```bash
pip3 install --user python-dotenv
```

#### Error: Bot doesn't respond to messages

**Cause:** Webhook not set or incorrect  
**Fix:**
1. Visit `/diag` endpoint to check webhook status
2. Check `.env` file has correct `WEBHOOK_HOST`
3. Make sure `USE_WEBHOOK=True` in `.env`
4. Check Error log for webhook errors

#### Error: "Invalid token" or webhook fails

**Cause:** Wrong bot token or webhook URL  
**Fix:**
1. Verify `TELEGRAM_BOT_TOKEN` in `.env` is correct
2. Check `WEBHOOK_HOST` matches your PythonAnywhere domain
3. Reload web app after fixing `.env`

### Deploying Multiple Bot Instances

If you want to run multiple bots on the same PythonAnywhere account:

**Bot 1 (Main):**
- Flask app path: `/home/goshadvoryak/single_sales_bot/webhook_app.py`
- Domain: `ysingle-goshadvoryak.pythonanywhere.com`
- Code location: `/home/goshadvoryak/single_sales_bot/`

**Bot 2:**
- Flask app path: `/home/goshadvoryak/single_sales_bot_2/webhook_app.py`
- Domain: Need second web app (requires paid account)
- Code location: `/home/goshadvoryak/single_sales_bot_2/`
- Different `.env` with different `TELEGRAM_BOT_TOKEN`

**Bot 3:**
- Flask app path: `/home/goshadvoryak/single_sales_bot_3/webhook_app.py`
- Domain: Need third web app (requires paid account)
- Code location: `/home/goshadvoryak/single_sales_bot_3/`
- Different `.env` with different `TELEGRAM_BOT_TOKEN`

**Note:** PythonAnywhere free accounts only support 1 web app. For multiple instances, you need a paid "Hacker" plan or higher.

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

