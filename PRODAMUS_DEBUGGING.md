# ProDAMUS Webhook Debugging Guide

## Quick Fix for 403 Errors

If you're getting 403 errors when ProDAMUS sends webhooks, follow these steps:

### Step 1: Enable Test Mode (Temporarily)

In your `.env` file, make sure:
```env
PRODAMUS_TEST_MODE=true
```

This will **skip signature verification** and let webhooks through. This helps determine if the issue is with signature verification or something else.

**⚠️ IMPORTANT:** Only use this for testing! Re-enable signature verification for production.

### Step 2: Check PythonAnywhere Error Log

1. Go to PythonAnywhere → Web tab
2. Click on "Error log" link
3. Look for ProDAMUS webhook logs

You should see detailed output like:
```
============================================================
ProDAMUS webhook received!
Headers: {'sign': 'abc123...', 'content-type': 'application/x-www-form-urlencoded'}
Form data: {'order_id': '123:course_1', 'payment_status': 'success', ...}
============================================================
ProDAMUS: TEST MODE - Skipping signature verification
ProDAMUS: ⚠️  WARNING: This should only be used for testing!
Signature valid: True
ProDAMUS webhook ACCEPTED: order_id=123:course_1, status=success
```

### Step 3: Test Payment Flow

With test mode enabled:
1. Select a course → Click ProDAMUS
2. Enter email
3. Click payment link
4. Complete test payment on ProDAMUS page
5. Check if bot grants access

**If it works:** The issue is signature verification  
**If it doesn't work:** The issue is elsewhere (check logs)

### Step 4: Fix Signature Verification (Production)

If test mode works but production doesn't, the signature verification is wrong.

#### Common Issues:

**Issue 1: Wrong Secret Key**
```env
# Make sure this matches EXACTLY what's in ProDAMUS dashboard
PRODAMUS_SECRET_KEY=your_actual_secret_key_here
```

**Issue 2: Extra Spaces in Secret Key**
```bash
# Bad (has trailing space):
PRODAMUS_SECRET_KEY=mysecret 

# Good:
PRODAMUS_SECRET_KEY=mysecret
```

**Issue 3: Special Characters in Secret Key**
If your secret key has special characters, make sure they're not being escaped or changed by the shell.

#### How to Debug Signature:

1. Set `PRODAMUS_TEST_MODE=false`
2. Make a test payment
3. Check error log for detailed signature debug output:

```
ProDAMUS: Verifying signature for 15 parameters
ProDAMUS: Sorted keys: ['attempt', 'commission', 'commission_sum', 'customer_email', ...]
ProDAMUS: Values string: 1;3.5;35.00;test@test.com;...
ProDAMUS: String to hash length: 245
ProDAMUS: Calculated signature: abc123def456...
ProDAMUS: Received signature:   xyz789ghi012...
ProDAMUS: Signatures match: False
ProDAMUS: ❌ Signature verification FAILED
```

#### Verify Secret Key in ProDAMUS Dashboard:

1. Log into ProDAMUS dashboard
2. Go to Settings → API/Webhooks
3. Copy the **exact** secret key
4. Update `.env` file
5. Reload web app on PythonAnywhere

### Step 5: Re-enable Production Mode

Once everything works:
```env
PRODAMUS_TEST_MODE=false
```

Then reload your web app.

## Detailed Debugging Steps

### Check 1: Webhook URL is Correct

In ProDAMUS dashboard, webhook URL should be:
```
https://ysingle-goshadvoryak.pythonanywhere.com/prodamus_webhook
```

**Common mistakes:**
- Missing `/prodamus_webhook` path
- HTTP instead of HTTPS
- Wrong domain name

### Check 2: ProDAMUS is Enabled

```bash
# Check config
cd ~/single_sales_bot
python3 -c "from config import ENABLE_PRODAMUS; print(f'ENABLE_PRODAMUS={ENABLE_PRODAMUS}')"
```

Should output: `ENABLE_PRODAMUS=True`

### Check 3: View Full Webhook Payload

Look for this in error log:
```
Headers: {'sign': '...', 'content-type': '...', ...}
Form data: {'order_id': '...', 'payment_status': '...', ...}
```

This shows **exactly** what ProDAMUS is sending.

### Check 4: Test Signature Calculation Manually

Create a test script `test_signature.py`:

```python
#!/usr/bin/env python3
import hashlib
from config import PRODAMUS_SECRET_KEY

# Copy actual data from your error log
test_data = {
    "order_id": "123:course_1",
    "payment_status": "success",
    "sum": "1000.00",
    "customer_email": "test@test.com",
    # ... add all other fields from webhook
}

# Sort and concatenate
sorted_keys = sorted(test_data.keys())
values_string = ";".join(str(test_data[key]) for key in sorted_keys)
string_to_hash = values_string + ";" + PRODAMUS_SECRET_KEY

# Calculate
signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

print(f"Calculated signature: {signature}")
print(f"\nString to hash: {string_to_hash}")
print(f"\nSorted keys: {sorted_keys}")
```

Run:
```bash
python3 test_signature.py
```

Compare calculated signature with what ProDAMUS sent.

### Check 5: Webhook Headers

ProDAMUS sends signature in **header**, not in form data.

Header name: `sign` (lowercase)

Make sure you're reading from headers:
```python
signature = request.headers.get("sign", "")
```

### Check 6: Test with curl

Manually send a test webhook:

```bash
curl -X POST https://ysingle-goshadvoryak.pythonanywhere.com/prodamus_webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "sign: test_signature_123" \
  -d "order_id=123:course_1&payment_status=success&sum=1000.00&customer_email=test@test.com"
```

Check error log to see if webhook was received.

## Common Error Messages

### "403 Forbidden"
**Cause:** Signature verification failed  
**Fix:** Enable test mode, check secret key, check signature calculation

### "404 Not Found"
**Cause:** `ENABLE_PRODAMUS=false` or wrong webhook URL  
**Fix:** Set `ENABLE_PRODAMUS=true` in `.env`, reload web app

### "500 Internal Server Error"
**Cause:** Python exception in webhook handler  
**Fix:** Check error log for full traceback

### "ProDAMUS: No signature provided in webhook"
**Cause:** ProDAMUS not sending `sign` header  
**Fix:** Check ProDAMUS dashboard webhook configuration

### "ProDAMUS: PRODAMUS_SECRET_KEY is not configured"
**Cause:** Missing `PRODAMUS_SECRET_KEY` in `.env`  
**Fix:** Add secret key to `.env`, reload web app

## Production Checklist

Before going live:

- [ ] `PRODAMUS_TEST_MODE=false`
- [ ] `PRODAMUS_SECRET_KEY` is correct
- [ ] Webhook URL is configured in ProDAMUS dashboard
- [ ] Test payment works end-to-end
- [ ] Access is granted after successful payment
- [ ] Access is denied after failed payment
- [ ] Admin receives payment notification
- [ ] Error log shows no errors

## Support

If you're still having issues:

1. **Copy full error log output** (last 50 lines)
2. **Copy your `.env` file** (hide sensitive values)
3. **Describe the exact steps** to reproduce the issue
4. **Share ProDAMUS webhook configuration** (screenshot)

This will help diagnose the problem quickly.

