# ProDAMUS Integration Guide

This document explains the ProDAMUS payment integration that has been added to the bot.

## Overview

ProDAMUS has been integrated as a second payment method alongside YooKassa. When enabled, users will see two payment options when purchasing a course:
- **YooKassa (Telegram)** - Native Telegram payments
- **ProDAMUS** - External payment page with short URLs

## Architecture

### Files Modified/Created

1. **config.py** - Added ProDAMUS configuration variables
2. **payments/prodamus.py** (NEW) - ProDAMUS payment handler with:
   - Payment link generation
   - URL shortening via redirect following
   - Webhook signature verification
   - Payment status parsing

3. **main.py** - Added `/prodamus_webhook` endpoint for payment notifications
4. **handlers/payment_handlers.py** - Added:
   - ProDAMUS payment flow with email collection
   - Webhook handler for payment completion
   - Email validation

5. **utils/keyboards.py** - Updated course buttons to show payment method selection
6. **README.md** - Updated with ProDAMUS documentation
7. **DEPLOYMENT.md** - Added ProDAMUS configuration instructions

## How It Works

### Payment Flow

1. **User selects course** → Bot shows payment method options
2. **User clicks "ProDAMUS"** → Bot asks for email address
3. **User sends email** → Bot validates email format
4. **Bot generates payment** → Creates long URL with parameters:
   ```
   https://demo.payform.ru/?order_id=USER_ID:COURSE_ID&customer_email=...&products[0][price]=...&do=pay
   ```
5. **Bot follows redirect** → Gets short URL like `https://demo.payform.ru/p/abc123`
6. **Bot sends link to user** → User clicks and pays on ProDAMUS page
7. **ProDAMUS sends webhook** → Payment notification to `/prodamus_webhook`
8. **Bot verifies signature** → Validates webhook authenticity
9. **Bot grants/denies access** → Based on payment status

### Webhook Signature Verification

According to ProDAMUS documentation:
1. Sort all webhook parameters alphabetically by key
2. Concatenate values with semicolons (`;`)
3. Append secret key
4. Calculate SHA256 hash
5. Compare with `sign` header

Example:
```python
# Parameters: {order_id: "123", sum: "1000", customer_email: "test@test.com"}
# Secret: "secret123"
values = "test@test.com;123;1000"  # Sorted alphabetically
string_to_hash = values + ";secret123"
signature = sha256(string_to_hash).hexdigest()
```

### Payment Data Structure

**Order ID Format:**
```
{user_id}:{course_id}
```
Example: `123456789:course_1`

**Payment Parameters Sent to ProDAMUS:**
- `order_id` - Unique identifier (user_id:course_id)
- `customer_email` - Required for receipt
- `customer_phone` - Optional
- `products[0][name]` - Course name
- `products[0][price]` - Price in rubles (integer)
- `products[0][quantity]` - Always 1
- `customer_extra` - Additional info (Telegram username)
- `do` - "pay" (initiates payment)

**Webhook Response from ProDAMUS:**
- `payment_status` - "success" or "error"
- `order_id` - Our order identifier
- `sum` - Payment amount
- `customer_email` - Buyer's email
- `payment_status_description` - Status description
- `sign` - Signature for verification

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# Enable ProDAMUS (set to true to activate)
ENABLE_PRODAMUS=false

# Test mode (true = test payments, false = production)
PRODAMUS_TEST_MODE=true

# Your ProDAMUS payment form URL
PRODAMUS_PAYFORM_URL=https://demo.payform.ru

# Secret key from ProDAMUS dashboard (for webhook signature verification)
PRODAMUS_SECRET_KEY=your_secret_key_here
```

### ProDAMUS Dashboard Setup

1. **Get your payment form URL** - e.g., `https://yourshop.payform.ru`
2. **Get secret key** - From ProDAMUS dashboard → Settings → API
3. **Configure webhook** - Set webhook URL to:
   ```
   https://yourdomain.com/prodamus_webhook
   ```
4. **Test the integration** - Use test mode first

## Testing

### Local Testing (Polling Mode)

1. Set environment variables in `.env`:
   ```env
   ENABLE_PRODAMUS=true
   PRODAMUS_TEST_MODE=true
   PRODAMUS_PAYFORM_URL=https://demo.payform.ru
   PRODAMUS_SECRET_KEY=test_secret_key
   USE_WEBHOOK=False
   ```

2. For local webhook testing, use ngrok:
   ```bash
   ngrok http 5000
   ```
   Then update ProDAMUS webhook URL to: `https://your-ngrok-url.ngrok.io/prodamus_webhook`

3. Run the bot:
   ```bash
   python main.py
   ```

4. Test payment flow:
   - Start bot → Select course → Click "ProDAMUS"
   - Enter email → Receive payment link
   - Complete test payment on ProDAMUS page
   - Bot should receive webhook and grant access

### Production Testing (Webhook Mode)

1. Deploy to PythonAnywhere with webhook enabled:
   ```env
   USE_WEBHOOK=True
   WEBHOOK_HOST=yourusername.pythonanywhere.com
   ENABLE_PRODAMUS=true
   PRODAMUS_TEST_MODE=true
   ```

2. Set ProDAMUS webhook URL:
   ```
   https://yourusername.pythonanywhere.com/prodamus_webhook
   ```

3. Test with small amounts first

4. Check logs:
   - PythonAnywhere → Web tab → Error log
   - Look for "ProDAMUS:" prefixed messages

### Webhook Verification

To manually test webhook signature verification:

```python
from payments.prodamus import verify_webhook_signature

test_data = {
    "order_id": "123:course_1",
    "payment_status": "success",
    "sum": "1000.00",
    "customer_email": "test@test.com"
}

test_signature = "6f47da9e9050fec913d013adb1990975d2d3ad86da2d6d35fc43df7344932e3e"

is_valid = verify_webhook_signature(test_data, test_signature)
print(f"Signature valid: {is_valid}")
```

## Security Considerations

1. **Signature Verification** - All webhooks are verified using SHA256 signature
2. **HTTPS Only** - ProDAMUS webhooks only work with HTTPS endpoints
3. **Secret Key Protection** - Keep `PRODAMUS_SECRET_KEY` in `.env`, never commit to git
4. **Email Validation** - Basic email format validation before creating payment
5. **Order ID Format** - Strictly validated to prevent injection attacks

## Error Handling

### Payment Link Generation Errors
- **Issue**: Cannot generate payment link
- **Cause**: Invalid PRODAMUS_PAYFORM_URL or network error
- **Solution**: Check URL format, test network connectivity

### Webhook Not Received
- **Issue**: Payment successful but no webhook received
- **Cause**: Webhook URL not configured or incorrect
- **Solution**: Verify webhook URL in ProDAMUS dashboard

### Signature Verification Failed
- **Issue**: Webhook rejected with 403 error
- **Cause**: Invalid secret key or parameter sorting issue
- **Solution**: Verify PRODAMUS_SECRET_KEY matches dashboard

### Email Collection Issues
- **Issue**: User stuck in email input mode
- **Cause**: User sends invalid email multiple times
- **Solution**: Bot re-prompts until valid email received. User can restart with /start

## Troubleshooting

### Debug Mode

Enable detailed logging by checking main.py output for "ProDAMUS:" prefixed messages:

```python
print(f"ProDAMUS: Generated payment link for order {order_id}")
print(f"ProDAMUS: Webhook received: order_id={order_id}, status={status}")
print(f"ProDAMUS: Signature verification failed")
```

### Common Issues

**Issue: Payment link is too long**
✅ **Fixed**: Bot follows redirects to get short URL automatically

**Issue: User email not collected**
✅ **Fixed**: Bot asks for email before generating payment link

**Issue: Webhook signature invalid**
- Check that PRODAMUS_SECRET_KEY is correct
- Verify parameters are sorted alphabetically
- Check that secret key doesn't have extra spaces

**Issue: Access not granted after payment**
- Check bot logs for webhook receipt
- Verify payment_status is "success"
- Check that order_id format is correct (user_id:course_id)

## Migration from YooKassa-Only

If you're upgrading from a YooKassa-only setup:

1. **Backward Compatible** - Existing YooKassa payments continue to work
2. **Optional Feature** - ProDAMUS is disabled by default
3. **No Database Changes** - Uses existing purchases table
4. **No Code Conflicts** - ProDAMUS and YooKassa handlers are independent

## API Reference

### `generate_payment_link()`
```python
def generate_payment_link(
    order_id: str,
    customer_email: str,
    customer_phone: str,
    product_name: str,
    price: float,
    customer_extra: str = ""
) -> str:
```
Generates ProDAMUS payment link and returns shortened URL.

### `verify_webhook_signature()`
```python
def verify_webhook_signature(
    data: dict,
    signature: str
) -> bool:
```
Verifies webhook signature using SHA256.

### `parse_webhook_data()`
```python
def parse_webhook_data(
    form_data: dict
) -> dict:
```
Parses ProDAMUS webhook form data.

### `is_payment_successful()`
```python
def is_payment_successful(
    webhook_data: dict
) -> bool:
```
Checks if payment was successful.

## Support

For ProDAMUS-specific issues:
- ProDAMUS Documentation: https://help.prodamus.ru/payform/integracii/rest-api/
- ProDAMUS Support: Check their website for contact info

For bot integration issues:
- Check bot logs for "ProDAMUS:" messages
- Verify environment variables are set correctly
- Test webhook URL is accessible from internet


