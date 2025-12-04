# Sales Bot - Clean and Modular

A simple, clean Telegram bot for selling courses with YooKassa and Prodamus payment integration.

## Features

- 🎯 Course catalog from Google Sheets
- 💳 Multiple payment methods:
  - YooKassa (via Telegram Payments API)
  - Prodamus (external payment gateway)
- 🔐 Private channel access management
- 📊 Admin panel with subscription management
- 🔄 Automatic subscription expiry handling
- 📱 Webhook and polling modes
- 📝 Structured logging
- 🖼️ Image caching and preloading

## Project Structure

```
single_sales_bot/
├── handlers/              # Bot command and callback handlers
│   ├── basic_handlers.py         # /start, support, oferta
│   ├── catalog_handlers.py       # Course catalog and viewing
│   ├── payment_handlers.py       # Payment processing (YooKassa & Prodamus)
│   └── admin_handlers.py         # Admin commands
├── payments/              # Payment integrations
│   ├── yookassa.py               # YooKassa payment handler
│   ├── prodamus.py               # Prodamus payment link generation
│   └── prodamus_webhook.py       # Prodamus webhook handler
├── utils/                 # Utility functions
│   ├── text_utils.py             # Text formatting and cleaning
│   ├── text_loader.py             # Text loading and caching
│   ├── keyboards.py               # Keyboard builders
│   ├── channel.py                 # Channel management
│   ├── images.py                  # Image caching and preloading
│   └── logger.py                  # Logging utility
├── config.py              # Configuration settings
├── db.py                   # Database operations
├── google_sheets.py        # Google Sheets integration
├── main.py                 # Main entry point
├── webhook_app.py          # WSGI application
└── requirements.txt        # Dependencies
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with the following variables:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Payments (YooKassa)
PAYMENT_PROVIDER_TOKEN=your_yookassa_token_here
CURRENCY=RUB
ENABLE_YOOKASSA=True  # Set to False to disable YooKassa payment button

# Payments (Prodamus) - Optional
PRODAMUS_SECRET_KEY=your_prodamus_secret_key
PRODAMUS_BASE_URL=https://demo.payform.ru

# Database
# Database
DATABASE_PATH=bot.db

# Google Sheets
GSHEET_ID=your_google_sheet_id
GSHEET_COURSES_NAME=Courses
GSHEET_TEXTS_NAME=Texts
GOOGLE_SHEETS_USE_API=False

# Admins (comma-separated Telegram user IDs)
ADMIN_IDS=123456789,987654321

# Webhook (for PythonAnywhere)
USE_WEBHOOK=False
WEBHOOK_HOST=yourusername.pythonanywhere.com
WEBHOOK_SECRET_TOKEN=your_secret_token
```

### 3. Google Sheets Setup

Create a Google Sheet with two tabs:

**Courses Tab:**
| id | name | description | price | duration_days | image_url | channel |
|----|------|-------------|-------|--------------|-----------|---------|
| 1  | Course Name | Course Description | 1000 | 30 | https://... | @channel_name |

**Texts Tab:**
| key | value |
|-----|-------|
| welcome_message | Welcome text |
| catalog_title | Catalog title |
| support_message | Support message |

Make the sheet public or use Google Sheets API with service account.

### 4. Run the Bot

**Polling Mode (local):**
```bash
python main.py
```

**Webhook Mode (PythonAnywhere):**
1. Set `USE_WEBHOOK=True` in `.env`
2. Upload code to PythonAnywhere
3. Set WSGI configuration to import `application` from `webhook_app`
4. Reload web app

## Admin Commands

- `/start` - Start the bot
- `/diag_channels` - Check channel permissions
- `/cleanup_expired` - Manually cleanup expired subscriptions
- `/broadcast_all <message>` - Broadcast to all users
- `/broadcast_buyers <message>` - Broadcast to users with purchases
- `/broadcast_nonbuyers <message>` - Broadcast to users without purchases

## Menu Buttons (Admin Only)

- 📊 Все подписки - View all active subscriptions
- 📋 Google Sheets - Open Google Sheets in browser

## Deployment on PythonAnywhere

1. Upload the code to your PythonAnywhere account
2. Create a web app (Python 3.10+)
3. Set the source code directory to `/home/yourusername/single_sales_bot`
4. In WSGI configuration file, add:
   ```python
   import sys
   path = '/home/yourusername/single_sales_bot'
   if path not in sys.path:
       sys.path.append(path)
   
   from webhook_app import application
   ```
5. Set `USE_WEBHOOK=True` in `.env`
6. Reload the web app

## Payment Methods

### YooKassa (via Telegram Payments)
Primary payment method using Telegram's native payment interface. Requires a provider token from BotFather linked to your YooKassa account.

**Note:** You can disable the YooKassa payment button by setting `ENABLE_YOOKASSA=False` in your `.env` file. When disabled, only the Prodamus payment option will be shown to users.

### Prodamus
Alternative payment gateway for external payments. Requires:
- `PRODAMUS_SECRET_KEY` - Secret key for webhook signature verification
- `PRODAMUS_BASE_URL` - Base URL of Prodamus payment form (default: https://demo.payform.ru)

The webhook endpoint is available at `/prodamus_webhook` and handles payment status updates automatically.

## Key Features

✅ **Modular structure** - Code organized into logical modules  
✅ **Multiple payment systems** - YooKassa and Prodamus support  
✅ **Clean code** - Well-organized, maintainable codebase  
✅ **Structured logging** - Centralized logging with proper levels  
✅ **Better error handling** - Proper exception handling throughout  
✅ **Clear separation of concerns** - Handlers, utils, payments separated  
✅ **Text caching** - Efficient text loading from Google Sheets  
✅ **Image caching** - Local image caching for faster delivery  
✅ **Easier maintenance** - Find and fix issues quickly  
✅ **Type hints ready** - Easy to add type hints if needed

## Development

### Code Style
- Use consistent formatting (PEP 8)
- Add docstrings to public functions
- Use the logging utility instead of print statements
- Keep functions focused and small

### Testing
Run the bot locally in polling mode for testing:
```bash
python main.py
```

### Logging
The bot uses structured logging via `utils.logger`. Log levels:
- `log_info()` - General information
- `log_warning()` - Warnings
- `log_error()` - Errors with optional exception info  

## License

Private project - All rights reserved
