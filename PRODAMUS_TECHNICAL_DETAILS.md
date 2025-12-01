# ProDAMUS Technical Details

## 🔧 How We Generate Payment Links

### Step-by-Step Process:

**1. User clicks "💰 ProDAMUS" button**
```python
# handlers/payment_handlers.py
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_pd_"))
def cb_pay_prodamus(c: types.CallbackQuery):
    # Store that we're waiting for email from this user
    _email_requests[user_id] = {"course_id": course_id, "step": "waiting_email"}
    # Ask user for email
    bot.send_message(user_id, "Please send your email:")
```

**2. User sends email**
```python
@bot.message_handler(content_types=['text'], func=lambda m: m.from_user.id in _email_requests)
def handle_email_input(message: types.Message):
    email = message.text.strip()
    # Validate email format
    if "@" not in email:
        return  # Ask again
    # Generate payment link
    payment_url = generate_payment_link(...)
```

**3. Generate payment link with parameters**

```python
# payments/prodamus.py - generate_payment_link()

# Step 1: Build parameters dictionary
params = {
    "order_id": "314112021:2",              # Format: user_id:course_id
    "customer_email": "user@example.com",    # Required!
    "products[0][price]": 102,               # Price in rubles (integer)
    "products[0][quantity]": 1,              # Always 1
    "products[0][name]": "Soft Matte",       # Course name
    "customer_extra": "Telegram bot purchase", # Optional info
    "do": "pay"                              # Trigger payment form
}

# Step 2: Build long URL
long_url = "https://beauty-glam-course.payform.ru?" + urlencode(params)
# Result: https://beauty-glam-course.payform.ru?order_id=314112021%3A2&customer_email=...

# Step 3: Make request to follow redirects
response = requests.get(long_url, allow_redirects=True, timeout=10)

# Step 4: Get final shortened URL
short_url = response.url
# Result: https://beauty-glam-course.payform.ru/p/abc123xyz

return short_url
```

**Example of what happens:**

```
LONG URL (generated):
https://beauty-glam-course.payform.ru?order_id=314112021:2&customer_email=user@example.com&products[0][price]=102&products[0][quantity]=1&products[0][name]=Soft+Matte&do=pay

                    ↓ (Python requests follows redirect)

SHORT URL (returned to user):
https://beauty-glam-course.payform.ru/p/x1y2z3
```

**4. Send short link to user**
```python
# Bot sends message with payment button
kb = types.InlineKeyboardMarkup()
kb.add(types.InlineKeyboardButton("💳 Pay", url=short_url))
bot.send_message(user_id, "Click to pay:", reply_markup=kb)
```

## 🔒 How We Verify Webhook Signature

### The Problem We Had:

❌ **OLD CODE (WRONG):** Used plain SHA256 hash
```python
# WRONG - This doesn't work!
string_to_hash = values_string + ";" + secret_key
calculated_signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
```

✅ **NEW CODE (CORRECT):** Uses HMAC-SHA256
```python
# CORRECT - ProDAMUS uses HMAC!
calculated_signature = hmac.new(
    secret_key.encode('utf-8'),    # Key
    values_string.encode('utf-8'), # Message
    hashlib.sha256                 # Hash algorithm
).hexdigest()
```

### Step-by-Step Signature Verification:

**1. ProDAMUS sends webhook**
```http
POST /prodamus_webhook HTTP/1.1
Host: ysingle-goshadvoryak.pythonanywhere.com
Content-Type: application/x-www-form-urlencoded
sign: 6f47da9e9050fec913d013adb1990975d2d3ad86da2d6d35fc43df7344932e3e

date=2025-12-01T00:00:00+03:00&order_id=314112021:2&order_num=test&sum=102.00&customer_email=user@example.com&payment_status=success
```

**2. We receive and parse the data**
```python
# main.py - _prodamus_webhook()
signature = request.headers.get("sign", "")  # Get from header
form_data = request.form.to_dict()           # Parse POST data

# Result:
form_data = {
    "date": "2025-12-01T00:00:00+03:00",
    "order_id": "314112021:2",
    "order_num": "test",
    "sum": "102.00",
    "customer_email": "user@example.com",
    "payment_status": "success",
    # ... more fields
}
```

**3. Calculate signature ourselves**
```python
# payments/prodamus.py - verify_webhook_signature()

# Step 1: Remove 'sign' field from data
filtered_data = {k: v for k, v in data.items() if k != 'sign'}

# Step 2: Sort keys alphabetically
sorted_keys = sorted(filtered_data.keys())
# Example: ['customer_email', 'date', 'order_id', 'order_num', 'payment_status', 'sum']

# Step 3: Join values with semicolons
values_string = ";".join(str(filtered_data[key]) for key in sorted_keys)
# Result: "user@example.com;2025-12-01T00:00:00+03:00;314112021:2;test;success;102.00"

# Step 4: Calculate HMAC-SHA256
calculated_signature = hmac.new(
    PRODAMUS_SECRET_KEY.encode('utf-8'),  # Key from .env
    values_string.encode('utf-8'),        # Message from step 3
    hashlib.sha256                        # Algorithm
).hexdigest()

# Step 5: Compare signatures
is_valid = hmac.compare_digest(calculated_signature, signature)
```

**4. Visual example:**

```
Parameters received:
{
    "customer_email": "user@example.com",
    "date": "2025-12-01T00:00:00+03:00",
    "order_id": "314112021:2",
    "payment_status": "success",
    "sum": "102.00"
}

        ↓ Sort alphabetically by key

Sorted keys:
["customer_email", "date", "order_id", "payment_status", "sum"]

        ↓ Join values with semicolons

Values string:
"user@example.com;2025-12-01T00:00:00+03:00;314112021:2;success;102.00"

        ↓ Calculate HMAC-SHA256 with secret key

HMAC(
    key = "your_secret_key_here",
    message = "user@example.com;2025-12-01T00:00:00+03:00;314112021:2;success;102.00",
    algorithm = SHA256
)

        ↓ Result

Calculated: 6f47da9e9050fec913d013adb1990975d2d3ad86da2d6d35fc43df7344932e3e
Received:   6f47da9e9050fec913d013adb1990975d2d3ad86da2d6d35fc43df7344932e3e

        ↓ Compare

✅ MATCH! Signature is valid.
```

## 📦 Using prodamuspy Library

The library handles this automatically:

```python
import prodamuspy

# Initialize with secret key
prodamus = prodamuspy.PyProdamus(PRODAMUS_SECRET_KEY)

# Parse form data (if it's query string)
body_dict = prodamus.parse(body)

# Verify signature (returns True/False)
is_valid = prodamus.verify(body_dict, received_signature)

if is_valid:
    print("Signature is valid!")
    # Process payment
else:
    print("Signature is invalid!")
    # Reject webhook
```

## 🔍 Key Differences: SHA256 vs HMAC-SHA256

### Plain SHA256 (WRONG):
```python
# What we were doing before (doesn't work with ProDAMUS)
string = "value1;value2;value3;secret_key"
signature = hashlib.sha256(string.encode()).hexdigest()

# Anyone can calculate this if they know the secret!
```

### HMAC-SHA256 (CORRECT):
```python
# What ProDAMUS actually uses
signature = hmac.new(
    key=secret_key.encode(),      # Secret key is separate
    msg="value1;value2;value3".encode(),  # Message to sign
    digestmod=hashlib.sha256
).hexdigest()

# Only someone with the secret key can generate valid signatures!
```

**Why HMAC is more secure:**
- Secret key is not part of the message
- Uses cryptographic HMAC algorithm
- Prevents tampering and replay attacks
- Industry standard for webhook verification

## 🚀 Installation Instructions

### On PythonAnywhere:

```bash
# 1. Open Bash console
cd ~/single_sales_bot

# 2. Update code (pull latest changes)
git pull  # If using git

# 3. Install new dependency
pip3 install --user prodamuspy

# 4. Reload web app
# Go to Web tab → Click green "Reload" button
```

### On Local Machine:

```bash
cd /Users/g.dvoryak/Desktop/single_sales_bot

# Install dependency
pip3 install prodamuspy

# Restart bot
python3 main.py
```

## 🧪 Testing

### Test Signature Verification Manually:

```python
#!/usr/bin/env python3
import hmac
import hashlib

# Your actual secret key from ProDAMUS dashboard
SECRET_KEY = "your_secret_key_here"

# Sample webhook data (from ProDAMUS)
data = {
    "customer_email": "test@test.com",
    "date": "2025-12-01T00:00:00+03:00",
    "order_id": "123:1",
    "payment_status": "success",
    "sum": "100.00"
}

# Sort and join
sorted_keys = sorted(data.keys())
values_string = ";".join(str(data[key]) for key in sorted_keys)

print(f"Sorted keys: {sorted_keys}")
print(f"Values string: {values_string}")

# Calculate HMAC
signature = hmac.new(
    SECRET_KEY.encode('utf-8'),
    values_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"Calculated signature: {signature}")
```

## 📋 Checklist for Production

- [ ] Install `prodamuspy` library
- [ ] Pull latest code with HMAC verification
- [ ] Set `PRODAMUS_TEST_MODE=false` in `.env`
- [ ] Verify `PRODAMUS_SECRET_KEY` matches dashboard
- [ ] Reload web app on PythonAnywhere
- [ ] Test real payment
- [ ] Check error log for "✅ Signature verification SUCCESS"
- [ ] Confirm access is granted automatically

## 🆘 If Still Not Working

1. **Check error log for:**
   ```
   ProDAMUS: Calculated signature: abc...
   ProDAMUS: Received signature:   xyz...
   ```

2. **Compare these values** - they should match!

3. **If they don't match:**
   - Verify secret key is correct (copy from ProDAMUS dashboard)
   - Check for extra spaces or newlines in secret key
   - Make sure you installed the library: `pip3 list | grep prodamus`
   - Reload web app after installing library

4. **Check library is loaded:**
   ```
   ProDAMUS: Using prodamuspy library for signature verification
   ```

5. **If using fallback:**
   ```
   ProDAMUS: Using manual HMAC-SHA256 verification
   ```
   This should also work, but library is preferred.

## 📚 References

- [ProDAMUS Documentation](https://help.prodamus.ru/payform/integracii/rest-api/instrukcii-dlya-samostoyatelnaya-integracii-servisov)
- [prodamuspy Library on GitHub](https://github.com/dnagikh/python-prodamus)
- [HMAC Explanation](https://en.wikipedia.org/wiki/HMAC)

