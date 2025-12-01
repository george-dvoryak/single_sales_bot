# Example ProDAMUS Webhook Logs

## 📋 What You'll See in Error Log

When a webhook arrives, you'll see comprehensive logging like this:

```
================================================================================
🔔 ProDAMUS WEBHOOK RECEIVED
================================================================================
⏰ Time: unknown
🌐 Remote IP: 185.71.76.0
📋 Method: POST
📝 Content-Type: application/x-www-form-urlencoded
📏 Content-Length: 837

📨 HEADERS:
  Host: ysingle-goshadvoryak.pythonanywhere.com
  Content-Type: application/x-www-form-urlencoded
  Content-Length: 837
  sign: 6f47da9e9050fec913d013adb199... (truncated)
  Accept: */*
  User-Agent: curl

================================================================================
STEP 0: Initialize prodamuspy library
================================================================================
🔑 Secret key length: 64 chars
🔑 Secret key (first 10 chars): your_secre...
✅ prodamuspy initialized successfully

================================================================================
STEP 1: Get raw body from webhook
================================================================================
📦 Raw body length: 837 bytes
📦 Raw body (first 300 chars):
date=2025-12-01T00%3A00%3A00%2B03%3A00&order_id=314112021%3A2&order_num=test&domain=beauty-glam-course.payform.ru&sum=102.00&customer_phone=%2B79999999999&customer_email=test%40domain.com&customer_extra=%D1%82%D0%B5%D1%81%D1%82&payment_type=%D0%9F%D0%BB%D0%B0%D1%81%D1%82%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D1%8F+%D0%BA%D0%B0%D1%80%D1%82...
📦 Raw body (last 100 chars):
...D0%B1%D1%83%D1%87%D0%B0%D1%8E%D1%89%D0%B8%D0%BC+%D0%BC%D0%B0%D1%82%D0%B5%D1%80%D0%B8%D0%B0%D0%BB%D0%B0%D0%BC

================================================================================
STEP 2: Parse body with prodamus.parse()
================================================================================
✅ Parsed successfully!
📊 Total fields parsed: 18

📋 All parsed fields:
  attempt: 1
  commission: 3.5
  commission_sum: 35.00
  customer_email: test@domain.com
  customer_extra: тест
  customer_phone: +79999999999
  date: 2025-12-01T00:00:00+03:00
  domain: beauty-glam-course.payform.ru
  order_id: 314112021:2
  order_num: test
  payment_status: success
  payment_status_description: Успешная оплата
  payment_type: Пластиковая карта Visa, MasterCard, МИР
  products: (nested dict with 1 items)
    0: (nested dict with 4 items)
      name: Soft Matte
      price: 102.00
      quantity: 1
      sum: 102.00
  sum: 102.00
  sys: test

================================================================================
STEP 3: Extract and verify signature
================================================================================
🔐 Signature from header: 6f47da9e9050fec913d013adb1990975d2d3ad86da2d6d35fc43df7344932e3e
🔐 Signature length: 64 chars

🔍 Calling prodamus.verify()...
   - body_dict keys: ['attempt', 'commission', 'commission_sum', 'customer_email', 'customer_extra', 'customer_phone', 'date', 'domain', 'order_id', 'order_num', 'payment_status', 'payment_status_description', 'payment_type', 'products', 'sum', 'sys']
   - signature: 6f47da9e9050fec913d013adb199...

🔍 Verification result: True

✅ SIGNATURE VERIFIED SUCCESSFULLY!

================================================================================
STEP 4: Check payment status and process
================================================================================
📋 Order ID: 314112021:2
📋 Order Number: test
💰 Payment Sum: 102.00 RUB
📧 Customer Email: test@domain.com
📱 Customer Phone: +79999999999
📅 Payment Date: 2025-12-01T00:00:00+03:00
💳 Payment Type: Пластиковая карта Visa, MasterCard, МИР
✅ Payment Status: success

📦 Products: {'0': {'name': 'Soft Matte', 'price': '102.00', 'quantity': '1', 'sum': '102.00'}}

🔍 Status check: payment_status.lower() = 'success'

================================================================================
✅ PAYMENT SUCCESSFUL - GRANTING ACCESS
================================================================================
👤 Processing payment for order: 314112021:2
💵 Amount: 102.00 RUB
📧 Email: test@domain.com

ProDAMUS: Successful payment for user 314112021, course 2
ProDAMUS: Successful payment for user 314112021, course 2

✅ Payment processed successfully!
================================================================================
```

## 🔍 If Signature is Invalid:

```
================================================================================
STEP 3: Extract and verify signature
================================================================================
🔐 Signature from header: wrong_signature_here
🔐 Signature length: 20 chars

🔍 Calling prodamus.verify()...
   - body_dict keys: ['order_id', 'payment_status', 'sum', ...]
   - signature: wrong_signature_here...

🔍 Verification result: False

================================================================================
❌ SIGNATURE VERIFICATION FAILED
================================================================================
⚠️  Webhook REJECTED due to invalid signature
📦 Order ID: 314112021:2
📦 Payment status: success
📦 Sum: 102.00
📦 Email: test@domain.com
================================================================================
```

## 📊 Log Structure

### Each webhook shows:

1. **Reception Info** 📨
   - Time, IP, method, headers
   - Content type and length

2. **Step 0: Initialization** 🔧
   - Secret key info
   - Library initialization status

3. **Step 1: Raw Body** 📦
   - Body length
   - First 300 characters
   - Last 100 characters (if long)

4. **Step 2: Parsing** 🔍
   - Number of fields parsed
   - **ALL fields and values** (including nested)
   - Products array details

5. **Step 3: Verification** 🔐
   - Signature from header
   - Signature length
   - All body_dict keys
   - Verification result

6. **Step 4: Processing** ✅
   - All extracted values:
     - Order ID, Order Number
     - Payment sum, status
     - Customer email, phone
     - Payment date, type
     - Products details
   - Status check result
   - Processing outcome

## 🎯 Key Information You Can See:

- ✅ **Every field** received from ProDAMUS
- ✅ **Every value** in the parsed dictionary
- ✅ **Nested structures** (like products array)
- ✅ **Signature verification** step-by-step
- ✅ **Status checks** with actual values
- ✅ **Processing flow** from start to finish

## 🔧 How to Use These Logs:

### If Payment Works:
Look for:
```
✅ SIGNATURE VERIFIED SUCCESSFULLY!
✅ PAYMENT SUCCESSFUL - GRANTING ACCESS
✅ Payment processed successfully!
```

### If Signature Fails:
Look for:
```
❌ SIGNATURE VERIFICATION FAILED
```
Then check:
- Secret key matches ProDAMUS dashboard
- Signature in header is present

### If Payment Status Wrong:
Look for:
```
🔍 Status check: payment_status.lower() = '...'
```
Check if it's "success" or something else

### To Debug Issues:
1. Copy entire log block (from first === to last ===)
2. Look at "All parsed fields" section
3. Check signature verification result
4. Check status check result
5. Share log block if you need help

## 📝 Example Use Cases:

### Check what ProDAMUS sends:
Look at "All parsed fields" section - you'll see EVERYTHING

### Verify signature calculation:
Look at Step 3 - shows body_dict keys used for verification

### Debug failed payments:
Look at Step 4 - shows exact status and description

### Check products data:
Look for "Products:" in parsed fields - shows nested structure

## 🎓 Benefits:

- 🔍 **Full visibility** - See every value at every step
- 🐛 **Easy debugging** - Pinpoint exact issue
- 📊 **Data validation** - Verify ProDAMUS sends correct data
- 🔐 **Security audit** - Track signature verification
- 📈 **Monitoring** - Track payment flow

With these detailed logs, you can see **exactly** what's happening at every step! 🎉

