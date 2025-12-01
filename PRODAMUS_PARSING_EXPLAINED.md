# ProDAMUS Body Parsing - Why We Use `prodamuspy.parse()`

## 🎯 The Key Insight

You correctly identified that we should use `request.get_data(as_text=True)` to get the raw body and then parse it with `prodamuspy.parse()` method!

## ❓ Why This Matters

### ProDAMUS Sends PHP-Style Arrays:

```
products[0][name]=Course+Name&products[0][price]=100&products[0][quantity]=1
```

Notice the `[0]` notation? This is PHP array syntax.

### Flask's `request.form.to_dict()` Doesn't Handle This Well:

```python
# Flask parses it as flat strings:
{
    "products[0][name]": "Course Name",      # ❌ Literal brackets in key
    "products[0][price]": "100",
    "products[0][quantity]": "1"
}
```

The brackets are treated as **literal characters** in the key name, not array notation!

### `prodamuspy.parse()` Handles It Correctly:

```python
# prodamuspy converts PHP arrays to nested dicts:
{
    "products": {
        "0": {
            "name": "Course Name",           # ✅ Proper nested structure
            "price": "100",
            "quantity": "1"
        }
    }
}
```

This is the **correct** Python dict structure that matches the PHP array!

## 🔍 How It Works

### Step 1: Get Raw Body

```python
raw_body = request.get_data(as_text=True)
# Result: "order_id=123&products[0][name]=Test&products[0][price]=100"
```

### Step 2: Parse with prodamuspy

```python
import prodamuspy
parser = prodamuspy.PyProdamus(SECRET_KEY)
form_data = parser.parse(raw_body)
```

**Behind the scenes** (from the library):
```python
def parse(self, body: str):
    # Step 1: Parse query string
    payload = dict(parse_qsl(body, keep_blank_values=True, strict_parsing=True))
    # Result: {"order_id": "123", "products[0][name]": "Test", ...}
    
    # Step 2: Convert PHP arrays to Python dicts
    payload_dict = self.__php2dict(payload)
    # Result: {"order_id": "123", "products": {"0": {"name": "Test", ...}}}
    
    return payload_dict
```

### Step 3: Use Parsed Data for Signature Verification

```python
# The parsed dict can now be used directly for signature verification
is_valid = verify_webhook_signature(form_data, signature)
```

## 🔧 What We Changed

### Before (Less Reliable):
```python
# Used Flask's form parser
form_data = request.form.to_dict()
# Problem: PHP arrays not converted to nested dicts
```

### After (Better):
```python
# Use raw body + prodamuspy parser
raw_body = request.get_data(as_text=True)
parser = prodamuspy.PyProdamus(SECRET_KEY)
form_data = parser.parse(raw_body)
# Benefit: PHP arrays properly converted to nested dicts
```

## 📊 Example Comparison

### Raw ProDAMUS Webhook Body:
```
order_id=314112021:2&order_num=test&sum=102.00&customer_email=test@test.com&products[0][name]=Soft+Matte&products[0][price]=102&products[0][quantity]=1&payment_status=success
```

### Parsed by Flask (Wrong):
```python
{
    'order_id': '314112021:2',
    'order_num': 'test',
    'sum': '102.00',
    'customer_email': 'test@test.com',
    'products[0][name]': 'Soft Matte',        # ❌ Flat structure
    'products[0][price]': '102',
    'products[0][quantity]': '1',
    'payment_status': 'success'
}
```

### Parsed by prodamuspy (Correct):
```python
{
    'order_id': '314112021:2',
    'order_num': 'test',
    'sum': '102.00',
    'customer_email': 'test@test.com',
    'products': {                             # ✅ Nested structure
        '0': {
            'name': 'Soft Matte',
            'price': '102',
            'quantity': '1'
        }
    },
    'payment_status': 'success'
}
```

## 🎯 Why It Matters for Signature Verification

ProDAMUS calculates signature based on the **flattened** representation:

```
Sorted keys: ['customer_email', 'order_id', 'order_num', 'payment_status', 'products[0][name]', 'products[0][price]', 'products[0][quantity]', 'sum']

Values string: "test@test.com;314112021:2;test;success;Soft Matte;102;1;102.00"
```

The `prodamuspy.parse()` method maintains the original key structure for signature calculation, which is why it works correctly!

## 🚀 What Happens Now

1. **Webhook arrives** → Raw body received
2. **Parse with prodamuspy** → Proper dict structure
3. **Verify signature** → Using prodamuspy.verify()
4. **Process payment** → Access granted!

All in one library, properly handling PHP arrays! 🎉

## 📝 Code Flow

```python
# main.py - _prodamus_webhook()

# Get raw body
raw_body = request.get_data(as_text=True)

# Parse with prodamuspy
import prodamuspy
parser = prodamuspy.PyProdamus(PRODAMUS_SECRET_KEY)
form_data = parser.parse(raw_body)

# Verify signature (also uses prodamuspy)
is_valid = verify_webhook_signature(form_data, signature)

# Process if valid
if is_valid:
    handle_prodamus_payment(bot, form_data)
```

## ✅ Benefits

1. **More Reliable** - Proper PHP array handling
2. **Consistent** - Same library for parsing and verification
3. **Correct** - Matches ProDAMUS expectations
4. **Cleaner** - Less code, better results

## 🎓 Lesson Learned

When integrating with PHP-based payment systems:
- Don't rely on Flask/Django's default form parsers
- PHP array notation needs special handling
- Use libraries designed for the specific platform
- Test with actual webhook data

Thank you for catching this! Using `request.get_data()` + `prodamuspy.parse()` is the **correct** approach! 👍

