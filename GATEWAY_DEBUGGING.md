# Gateway/Proxy Body Modification Debugging

## 🎯 The Hypothesis

Your PythonAnywhere gateway might be modifying the request body between ProDAMUS and your Flask app, which would cause signature verification to fail because:

1. ProDAMUS signs the **original** body
2. Gateway modifies the body (URL decoding, re-encoding, etc.)
3. Your app receives the **modified** body
4. Signature calculated from modified body ≠ ProDAMUS signature
5. Verification fails! ❌

## 🔍 What the New Debug Logs Will Show

### **Check 1: Raw Body Integrity**

```
📦 Raw body length: 837 bytes
📦 request.content_length: 837
📦 Match: True ✅
```

**If they DON'T match:** Gateway modified the body length!

### **Check 2: Body Hash**

```
📦 Raw body MD5 hash: abc123def456...
```

We can compare this hash across multiple webhook attempts. If it changes for the same payment, the body is being modified!

### **Check 3: Proxy Detection**

```
🔍 PROXY/GATEWAY CHECK:
  ⚠️  X-Forwarded-For: 185.71.76.0
  ⚠️  Via: 1.1 pythonanywhere-proxy
```

**If you see proxy headers:** PythonAnywhere is using a proxy/gateway.

### **Check 4: Flask vs prodamus.parse() Comparison**

```
📦 Flask request.form keys: ['order_id', 'sum', 'customer_email', 'products[0][name]']
📦 prodamus.parse() keys: ['order_id', 'sum', 'customer_email', 'products']
```

**Notice the difference?**
- Flask: `products[0][name]` (flat, literal brackets)
- prodamuspy: `products` (nested dict)

This is expected! But if verification fails...

### **Check 5: Signature Recreation Test**

```
🔍 SIGNATURE INTEGRITY CHECK:
🔐 Calculated signature (from parsed data): xyz789abc123...
🔐 Received signature (from header):        xyz789abc123...
🔐 Signatures match: True ✅
```

**If they DON'T match:**
```
🔐 Signatures match: False ❌
⚠️  WARNING: Signatures don't match!
This suggests either:
  1. The request body was modified by a proxy/gateway
  2. The secret key is incorrect
  3. ProDAMUS is calculating signature differently
```

### **Check 6: Alternative Parsing Methods**

```
🔍 Trying verification with Flask's request.form:
   Verification with Flask data: True ✅

🔍 Trying different parsing methods:
   Verification with parse_qsl: True ✅
```

**If Flask data works but prodamus.parse() doesn't:**
- Issue is with how prodamuspy parses PHP arrays
- Solution: Use Flask's `request.form.to_dict()` instead

**If parse_qsl works:**
- Issue is with prodamus.parse() converting nested structures
- Solution: Use `parse_qsl` for parsing

## 🎯 Possible Scenarios

### Scenario 1: Gateway modifying body ⚠️

**Symptoms:**
- Raw body length ≠ content-length
- Calculated signature ≠ received signature
- Proxy headers present

**Solution:**
- Contact PythonAnywhere support
- Use alternative verification (skip signature, verify order in database)
- Use different hosting platform

### Scenario 2: Parsing issue ✅ (Most likely!)

**Symptoms:**
- Flask data verifies successfully
- prodamus.parse() data fails verification
- Calculated signature ≠ received signature

**Solution:**
```python
# Use Flask's form parsing instead of prodamus.parse()
body_dict = request.form.to_dict()
is_valid = prodamus.verify(body_dict, received_sign)
```

### Scenario 3: Wrong secret key ❌

**Symptoms:**
- All parsing methods fail
- Calculated ≠ received (completely different)
- No proxy headers

**Solution:**
- Verify secret key in `.env`
- Copy exact key from ProDAMUS dashboard
- Check for extra spaces/newlines

### Scenario 4: Everything works! ✅

**Symptoms:**
- All verifications pass
- Calculated = received
- No proxy modification

**Result:** Payment processes successfully!

## 📋 What to Look For

After deploying this code and making a test payment, look for these patterns in the error log:

### Pattern 1: Body Modified
```
📦 request.content_length: 837
📦 len(raw_body): 842
📦 Match: False  ⚠️  ← Body was modified!

⚠️  WARNING: Signatures don't match!
  1. The request body was modified by a proxy/gateway  ← This is the issue!
```

### Pattern 2: Parsing Issue
```
📦 Match: True ✅  ← Body not modified
🔐 Calculated signature: abc123...
🔐 Received signature:   xyz789...
🔐 Signatures match: False  ← But signatures don't match

Verification with Flask data: True ✅  ← Flask parsing works!
```

### Pattern 3: Wrong Secret Key
```
📦 Match: True ✅
🔐 Signatures match: False ❌
Verification with Flask data: False ❌  ← All methods fail
Verification with parse_qsl: False ❌
```

## 🚀 Deploy and Test

```bash
cd ~/single_sales_bot
git pull
# Reload web app
```

Then make a test payment and share the complete log output. The logs will tell us **exactly** what's wrong! 🔍

## 🔧 Quick Fixes Based on Results

### If Flask parsing works:
Change line in main.py:
```python
# Instead of:
body_dict = prodamus.parse(raw_body)

# Use:
body_dict = request.form.to_dict()
```

### If parse_qsl works:
```python
from urllib.parse import parse_qsl
body_dict = dict(parse_qsl(raw_body, keep_blank_values=True))
```

### If body is modified:
Enable test mode temporarily:
```env
PRODAMUS_TEST_MODE=true
```

The comprehensive logging will reveal the exact issue! 🎯

