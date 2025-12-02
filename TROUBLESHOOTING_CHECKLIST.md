# Troubleshooting Checklist - Website Not Showing "OK"

If your website at `https://ysingle-goshadvoryak.pythonanywhere.com/` is not showing "OK", follow this checklist:

## Step 1: Check PythonAnywhere Error Log

1. Go to PythonAnywhere **Web** tab
2. Click on **"Error log"** link
3. Read the **last 50-100 lines** of the error log
4. Look for:
   - `SyntaxError` - means there's a syntax error in your code
   - `ModuleNotFoundError` - means a Python package is missing
   - `ImportError` - means a module can't be imported
   - `ValueError` - usually means a config value is missing
   - `FileNotFoundError` - means a file is missing

**Write down the exact error message** - this is the most important step!

## Step 2: Verify File Structure on PythonAnywhere

Check that these files exist at `/home/goshadvoryak/single_sales_bot/`:

- [ ] `webhook_app.py` - **MUST EXIST**
- [ ] `main.py` - **MUST EXIST**
- [ ] `config.py` - **MUST EXIST**
- [ ] `.env` - **MUST EXIST** (hidden file, use `ls -la` to see it)
- [ ] `requirements.txt` - **MUST EXIST**
- [ ] `db.py` - **MUST EXIST**
- [ ] `handlers/` directory with all handler files
- [ ] `utils/` directory
- [ ] `payments/` directory

**To check:** Open PythonAnywhere **Files** tab, navigate to `/home/goshadvoryak/single_sales_bot/`

## Step 3: Check for Merge Conflict Markers

1. Open `/home/goshadvoryak/single_sales_bot/webhook_app.py` in PythonAnywhere Files tab
2. Look at the **first line** of the file
3. If you see any of these, you have merge conflicts:
   - `<<<<<<< Updated upstream`
   - `=======`
   - `>>>>>>> Stashed changes`

**Fix:** Remove all merge conflict markers and keep only the correct code. The file should start with:
```python
# webhook_app.py
```

## Step 4: Verify WSGI Configuration

1. Go to PythonAnywhere **Web** tab
2. Click on the **WSGI configuration file** link (usually `/var/www/ysingle_goshadvoryak_pythonanywhere_com_wsgi.py`)
3. Verify it contains **EXACTLY** this:

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

**Important:** 
- Path must be `/home/goshadvoryak/single_sales_bot` (not `/home/goshadvoryak/single_sales_bot/`)
- Must end with `from webhook_app import application`
- No extra code, no comments after the import

## Step 5: Verify .env File

1. Open `/home/goshadvoryak/single_sales_bot/.env` in PythonAnywhere Files tab
2. Check that it contains **ALL** required variables:

```env
TELEGRAM_BOT_TOKEN=your_token_here
PAYMENT_PROVIDER_TOKEN=your_token_here
GSHEET_ID=your_sheet_id
ADMIN_IDS=your_telegram_id
USE_WEBHOOK=True
WEBHOOK_HOST=ysingle-goshadvoryak.pythonanywhere.com
```

**Common issues:**
- Missing `TELEGRAM_BOT_TOKEN` → Will cause `ValueError` on import
- Missing `ADMIN_IDS` → Will cause `ValueError` on import
- Missing `GSHEET_ID` → Will cause `ValueError` on import
- `WEBHOOK_HOST` has wrong domain → Webhook won't work but app should still start

## Step 6: Check Dependencies Installation

1. Open PythonAnywhere **Bash** console
2. Run:
```bash
cd ~/single_sales_bot
pip3 install --user -r requirements.txt
```

3. Wait for installation to complete
4. If you see errors, note them down

**Common missing packages:**
- `telebot` → Install: `pip3 install --user pyTelegramBotAPI`
- `flask` → Install: `pip3 install --user flask`
- `dotenv` → Install: `pip3 install --user python-dotenv`
- `gspread` → Install: `pip3 install --user gspread` (if using Google Sheets API)

## Step 7: Test Import Manually

1. Open PythonAnywhere **Bash** console
2. Run:
```bash
cd ~/single_sales_bot
python3 -c "from webhook_app import application; print('SUCCESS')"
```

**If this fails:**
- The error message will tell you exactly what's wrong
- Common issues:
  - Missing `.env` file → Create it
  - Missing config values → Add them to `.env`
  - Missing Python packages → Install them
  - Syntax errors in code → Fix them

## Step 8: Check File Permissions

1. Open PythonAnywhere **Bash** console
2. Run:
```bash
cd ~/single_sales_bot
ls -la
```

3. Check that:
   - Files are readable (should show `-rw-r--r--` or similar)
   - `.env` file exists and is readable
   - `bot.db` file exists (or will be created automatically)

## Step 9: Verify Source Code Path

1. Go to PythonAnywhere **Web** tab
2. In the **"Code"** section, verify:
   - **Source code:** `/home/goshadvoryak/single_sales_bot`
   - **Working directory:** `/home/goshadvoryak/single_sales_bot`

**Important:** No trailing slash!

## Step 10: Reload Web App

1. Go to PythonAnywhere **Web** tab
2. Click the big green **"Reload"** button
3. Wait for the success message
4. If it shows an error, go back to Step 1 and check the error log

## Step 11: Test the Endpoint

1. Visit: `https://ysingle-goshadvoryak.pythonanywhere.com/`
2. Should show: `OK`
3. If it shows an error page, check the error log again

## Common Error Messages and Fixes

### "SyntaxError: invalid syntax" at line 1
**Cause:** Merge conflict markers in `webhook_app.py`  
**Fix:** Remove all `<<<<<<<`, `=======`, `>>>>>>>` lines from the file

### "ModuleNotFoundError: No module named 'webhook_app'"
**Cause:** WSGI file can't find your code  
**Fix:** 
- Check WSGI file has correct path (Step 4)
- Verify files exist at `/home/goshadvoryak/single_sales_bot/` (Step 2)

### "ModuleNotFoundError: No module named 'telebot'"
**Cause:** Dependencies not installed  
**Fix:** Run `pip3 install --user -r requirements.txt` (Step 6)

### "ValueError: TELEGRAM_BOT_TOKEN is required"
**Cause:** Missing token in `.env` file  
**Fix:** Add `TELEGRAM_BOT_TOKEN=your_token` to `.env` file (Step 5)

### "ValueError: ADMIN_IDS is required"
**Cause:** Missing admin IDs in `.env` file  
**Fix:** Add `ADMIN_IDS=your_telegram_id` to `.env` file (Step 5)

### "ImportError: cannot import name 'application' from 'main'"
**Cause:** `main.py` failed to create the Flask app  
**Fix:** Check error log for the actual error in `main.py` (usually a config or import issue)

### Website shows error page with traceback
**Cause:** An exception occurred during import  
**Fix:** 
1. Read the full traceback in the error page
2. Find the first error (usually at the bottom)
3. Fix that specific issue
4. Reload web app

## Still Not Working?

If you've gone through all steps and it's still not working:

1. **Copy the full error log** from PythonAnywhere (last 100 lines)
2. **Check the exact error message** - it will tell you what's wrong
3. **Verify all files are uploaded** - sometimes files don't upload correctly
4. **Try a fresh deployment:**
   - Delete everything in `/home/goshadvoryak/single_sales_bot/`
   - Re-upload all files
   - Re-run `pip3 install --user -r requirements.txt`
   - Re-create `.env` file
   - Reload web app

## Quick Test Script

Run this in PythonAnywhere Bash to test everything:

```bash
cd ~/single_sales_bot
echo "Testing imports..."
python3 -c "import sys; sys.path.insert(0, '.'); from config import TELEGRAM_BOT_TOKEN; print('Config OK')"
python3 -c "import sys; sys.path.insert(0, '.'); from main import application; print('Main OK')"
python3 -c "import sys; sys.path.insert(0, '.'); from webhook_app import application; print('Webhook app OK')"
echo "All tests passed!"
```

If any test fails, the error message will tell you what's wrong.

