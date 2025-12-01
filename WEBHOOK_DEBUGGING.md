# ProDAMUS Webhook Debugging - What You'll See in Logs

## 🐛 What Was Wrong

You had a bug in the code:
```python
# ❌ WRONG - variable mismatch
raw_body = request.get_data(as_text=True)  # String
is_valid = verify_webhook_signature(form_data, signature)  # form_data not defined!
```

The code was getting the raw body but not parsing it, then trying to use `form_data` which didn't exist!

## ✅ What I Fixed

Now the code:
1. Gets raw body for logging
2. Properly parses it as form data
3. Has fallback parsing if Flask doesn't auto-parse
4. Returns proper JSON responses instead of aborting
5. Has comprehensive logging at every step

## 📋 What You'll See in Error Log Now

### When Webhook Arrives:

```
============================================================
ProDAMUS webhook received!
Method: POST
Content-Type: application/x-www-form-urlencoded
Headers: {'sign': 'abc123...', 'content-type': 'application/x-www-form-urlencoded', ...}
Raw body: order_id=314112021:2&payment_status=success&sum=102.00&customer_email=test@test.com...
Parsed form data keys: ['order_id', 'payment_status', 'sum', 'customer_email', ...]
Parsed form data: {'order_id': '314112021:2', 'payment_status': 'success', ...}
============================================================
Signature from header: '6f47da9e9050fec913d013adb1990975d2d3ad86...'
```

### During Signature Verification:

```
ProDAMUS: Starting signature verification
ProDAMUS: Received signature: 6f47da9e9050fec913d013adb1990975d2d3ad86...
ProDAMUS: Using prodamuspy library for verification
ProDAMUS: ✅ Signature verification SUCCESS (prodamuspy)
Signature valid: True
```

**OR if it fails:**

```
ProDAMUS: Starting signature verification
ProDAMUS: Received signature: 6f47da9e9050fec913d013adb1990975d2d3ad86...
ProDAMUS: Using prodamuspy library for verification
ProDAMUS: ❌ Signature verification FAILED (prodamuspy)
Signature valid: False
============================================================
❌ ProDAMUS webhook: Invalid signature - REJECTED
Order ID: 314112021:2
Payment status: success
Customer email: test@test.com
Sum: 102.00
============================================================
```

### If Signature is Valid:

```
============================================================
✅ ProDAMUS webhook ACCEPTED!
Order ID: 314112021:2
Payment status: success
Sum: 102.00
Customer email: test@test.com
============================================================
ProDAMUS: Successful payment for user 314112021, course 2
✅ Payment processed successfully
```

## 🔍 How to Read the Logs

### 1. Check if webhook is received:
Look for:
```
ProDAMUS webhook received!
Method: POST
```

If you **don't see this**, ProDAMUS is not sending webhooks to your URL.

### 2. Check the signature in header:
Look for:
```
Signature from header: '6f47da9e...'
```

If it says `''` (empty), ProDAMUS is not sending the signature.

### 3. Check form data:
Look for:
```
Parsed form data: {'order_id': '...', 'payment_status': '...'}
```

If you see `{}` (empty), the body is not being parsed correctly.

### 4. Check signature verification:
Look for:
```
ProDAMUS: ✅ Signature verification SUCCESS
```

If you see `❌ FAILED`, the secret key is wrong.

### 5. Check payment processing:
Look for:
```
✅ ProDAMUS webhook ACCEPTED!
ProDAMUS: Successful payment for user...
```

If payment is processed successfully, the user should receive access.

## 🚀 Next Steps

### Deploy to PythonAnywhere:

```bash
# 1. Upload updated code
cd ~/single_sales_bot
git pull  # or upload manually

# 2. Install prodamuspy if not installed
pip3 install --user prodamuspy

# 3. Check .env
cat .env | grep PRODAMUS

# 4. Reload web app
# Go to Web tab → Click "Reload"
```

### Test Payment:

1. Make a test payment through bot
2. Go to Web tab → Error log
3. Look for the detailed logs shown above
4. Share the logs if something is wrong

## 🔧 Common Issues

### Issue 1: Empty form data
```
Parsed form data: {}
ERROR: No form data received!
```

**Cause:** Content-Type header is wrong or body is malformed  
**Fix:** Check ProDAMUS is sending `application/x-www-form-urlencoded`

### Issue 2: No signature in header
```
Signature from header: ''
```

**Cause:** ProDAMUS not sending signature  
**Fix:** Check ProDAMUS dashboard webhook configuration

### Issue 3: Signature verification fails
```
ProDAMUS: ❌ Signature verification FAILED
```

**Cause:** Wrong secret key  
**Fix:** Copy exact secret key from ProDAMUS dashboard to `.env`

### Issue 4: prodamuspy not available
```
ProDAMUS: Warning - prodamuspy library not installed
ProDAMUS: Using manual HMAC-SHA256 verification
```

**Not an error!** Fallback verification will work, but install library:
```bash
pip3 install --user prodamuspy
```

## 📞 If You Need Help

When asking for help, share:
1. **The complete log section** starting from `ProDAMUS webhook received!`
2. **Your .env settings** (hide the actual secret key, just show if it's set):
   ```bash
   ENABLE_PRODAMUS=true
   PRODAMUS_SECRET_KEY=***hidden***  # Length: 64 chars
   ```
3. **ProDAMUS dashboard screenshot** showing webhook URL and settings

With these logs, we can immediately see what's wrong!

