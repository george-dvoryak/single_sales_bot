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

# Database
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

## Setting Up Scheduled Task for Expired Subscriptions Cleanup

The bot includes an automatic cleanup job that removes users from channels when their subscriptions expire. This job runs via a scheduled task in PythonAnywhere.

### Step 1: Get Your Webhook URL and Secret Token

From your `.env` file, note:
- `WEBHOOK_HOST` (e.g., `yourusername.pythonanywhere.com`)
- `WEBHOOK_SECRET_TOKEN` (your secret token)

The cleanup endpoint will be: `https://yourusername.pythonanywhere.com/cleanup_expired_job`

### Step 2: Create Scheduled Task in PythonAnywhere

1. Go to **Tasks** tab in PythonAnywhere dashboard
2. Click **"Create a new scheduled task"**
3. Configure the task:
   - **Command:** 
     ```bash
     curl -X POST https://yourusername.pythonanywhere.com/cleanup_expired_job -H "Authorization: Bearer YOUR_WEBHOOK_SECRET_TOKEN"
     ```
     Replace `yourusername` and `YOUR_WEBHOOK_SECRET_TOKEN` with your actual values.
   
   - **Hour:** Choose a time (e.g., `3` for 3 AM)
   - **Minute:** `0` (start of the hour)
   - **Enabled:** ✅ Check this box

4. Click **"Create"**

### Step 3: Test the Endpoint Manually

You can test the endpoint before setting up the scheduled task:

```bash
curl -X POST https://yourusername.pythonanywhere.com/cleanup_expired_job \
  -H "Authorization: Bearer YOUR_WEBHOOK_SECRET_TOKEN"
```

Expected response:
```json
{
  "status": "success",
  "expired_count": 0,
  "active_count": 5,
  "processed": 0,
  "failed": 0
}
```

### Alternative: Using Python Script in Scheduled Task

If you prefer, you can create a Python script instead:

1. Create file `~/cleanup_job.py`:
```python
import requests
import os

WEBHOOK_URL = "https://yourusername.pythonanywhere.com/cleanup_expired_job"
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "your_secret_token_here")

response = requests.post(
    WEBHOOK_URL,
    headers={"Authorization": f"Bearer {SECRET_TOKEN}"}
)
print(response.text)
```

2. In PythonAnywhere Tasks, set:
   - **Command:** `python3.10 ~/cleanup_job.py`
   - **Hour:** `3`
   - **Minute:** `0`

### What the Job Does

- Finds all subscriptions where `expiry <= current_time` and `expiry > 0`
- Removes users from their course channels
- Marks subscriptions as processed (sets `expiry = 0`)
- Sends notification messages to users about expired access
- Sends summary report to all admins

### Monitoring

- Check PythonAnywhere **Tasks** tab to see task execution history
- Check bot logs for cleanup job entries
- Admins receive Telegram notifications after each cleanup run

## Updating Code

```bash
cd ~/single_sales_bot
git pull
# Reload web app in PythonAnywhere
```

