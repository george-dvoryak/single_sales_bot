# payments/hmac_verifier.py
"""HMAC signature verification for ProDAMUS webhooks (exact PHP match)."""

import hmac
import hashlib
import json
from typing import Any, Dict, List, Union

JSONType = Union[Dict[str, Any], List[Any]]


class HmacPy:
    """HMAC signature creation and verification - exact PHP match."""

    # ---------- ПУБЛИЧНЫЕ МЕТОДЫ ----------

    @staticmethod
    def create(data: Any, key: str, algo: str = "sha256") -> str | None:
        """
        Create HMAC signature from data (exact PHP match).
        
        Args:
            data: Data to sign (dict, list, or JSON string)
            key: Secret key for HMAC
            algo: Hash algorithm (default: 'sha256')
        
        Returns:
            HMAC signature as hex string, or None on error
        """
        print("=" * 80)
        print("🔐 HmacPy.create() - Starting signature creation")
        print("=" * 80)
        print(f"📦 Input data type: {type(data).__name__}")
        print(f"🔑 Key length: {len(key)} chars")
        print(f"🔧 Algorithm: {algo}")
        
        digestmod = HmacPy._get_digestmod(algo)
        if digestmod is None:
            print(f"❌ Algorithm '{algo}' not available")
            return None  # как false в PHP

        # (array)$data — приводим к "массиву" (dict/list).
        print(f"\n📋 Step 1: Converting to array/dict (PHP array cast)")
        array_data = HmacPy._php_array_cast(data)
        print(f"   Result type: {type(array_data).__name__}")
        if isinstance(array_data, dict):
            print(f"   Keys count: {len(array_data)}")
            print(f"   Keys: {list(array_data.keys())[:10]}...")

        # array_walk_recursive + strval
        print(f"\n📋 Step 2: Converting all values to strings (strval)")
        array_data = HmacPy._to_str_values(array_data)
        print(f"   ✅ All values converted to strings")

        # рекурсивная сортировка по ключам (ksort + _sort)
        print(f"\n📋 Step 3: Recursively sorting by keys (ksort)")
        array_data = HmacPy._sort_recursive(array_data)
        if isinstance(array_data, dict):
            sorted_keys = list(array_data.keys())
            print(f"   Sorted keys: {sorted_keys[:10]}...")

        # json_encode(..., JSON_UNESCAPED_UNICODE)
        print(f"\n📋 Step 4: JSON encoding (JSON_UNESCAPED_UNICODE)")
        json_str = HmacPy._php_json_encode_unicode(array_data)
        print(f"   JSON string length: {len(json_str)} chars")
        print(f"   JSON preview (first 200 chars): {json_str[:200]}...")
        if len(json_str) > 200:
            print(f"   JSON preview (last 100 chars): ...{json_str[-100:]}")

        # hash_hmac($algo, $data, $key)
        print(f"\n📋 Step 5: Calculating HMAC")
        print(f"   Key bytes: {len(key.encode('utf-8'))} bytes")
        print(f"   Data bytes: {len(json_str.encode('utf-8'))} bytes")
        mac = hmac.new(key.encode("utf-8"), json_str.encode("utf-8"), digestmod)
        signature = mac.hexdigest()  # hex, как в PHP (строчные буквы)
        
        print(f"\n✅ Signature created successfully!")
        print(f"   Signature: {signature}")
        print(f"   Signature length: {len(signature)} chars")
        print("=" * 80)
        
        return signature

    @staticmethod
    def verify(data: Any, key: str, sign: str, algo: str = "sha256") -> bool:
        """
        Verify HMAC signature (exact PHP match).
        
        Args:
            data: Data to verify (dict, list, or JSON string)
            key: Secret key for HMAC
            sign: Received signature to verify against
            algo: Hash algorithm (default: 'sha256')
        
        Returns:
            True if signature is valid, False otherwise
        """
        print("=" * 80)
        print("🔍 HmacPy.verify() - Starting signature verification")
        print("=" * 80)
        print(f"📦 Data type: {type(data).__name__}")
        print(f"🔑 Key length: {len(key)} chars")
        print(f"🔐 Received signature: {sign}")
        print(f"🔐 Received signature length: {len(sign)} chars")
        print(f"🔧 Algorithm: {algo}")
        
        calc = HmacPy.create(data, key, algo)
        if not calc:
            print(f"\n❌ Failed to create signature - verification failed")
            print("=" * 80)
            return False

        # приведение к нижнему регистру + безопасное сравнение
        calc_lower = calc.lower()
        sign_lower = str(sign).lower()
        
        print(f"\n📋 Step 6: Comparing signatures (case-insensitive)")
        print(f"   Calculated (lowercase): {calc_lower}")
        print(f"   Received (lowercase):    {sign_lower}")
        
        is_valid = hmac.compare_digest(calc_lower, sign_lower)
        
        if is_valid:
            print(f"\n✅ SIGNATURE VERIFICATION SUCCESSFUL!")
        else:
            print(f"\n❌ SIGNATURE VERIFICATION FAILED!")
            # Show first difference
            min_len = min(len(calc_lower), len(sign_lower))
            for i in range(min_len):
                if calc_lower[i] != sign_lower[i]:
                    print(f"   First difference at position {i}: '{calc_lower[i]}' vs '{sign_lower[i]}'")
                    print(f"   Calculated: ...{calc[max(0,i-10):i+10]}...")
                    print(f"   Received:   ...{sign[max(0,i-10):i+10]}...")
                    break
            if len(calc_lower) != len(sign_lower):
                print(f"   Length mismatch: calculated={len(calc_lower)}, received={len(sign_lower)}")
        
        print("=" * 80)
        return is_valid

    # ---------- ВНУТРЕННИЕ ХЕЛПЕРЫ (АНАЛОГИ PHP) ----------

    @staticmethod
    def _get_digestmod(algo: str):
        """Get hash function from algorithm name."""
        try:
            return getattr(hashlib, algo)
        except AttributeError:
            return None

    @staticmethod
    def _php_array_cast(data: Any) -> JSONType:
        """
        Convert data to array/dict (like PHP (array)$data).
        """
        # Если это строка — сначала пробуем JSON
        if isinstance(data, str):
            stripped = data.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(data)
                    # дальше снова через _php_array_cast,
                    # чтобы всё равно получился dict/list
                    return HmacPy._php_array_cast(parsed)
                except Exception:
                    # не JSON — ведём себя как (array)$string => [string]
                    return [data]
            # обычная строка, не JSON
            return [data]

        # Если это dict — просто копия
        if isinstance(data, dict):
            return dict(data)

        # Если это list — просто копия
        if isinstance(data, list):
            return list(data)

        # Скаляр -> [скаляр] (как (array)$scalar в PHP)
        return [data]

    @staticmethod
    def _to_str_values(value: Any) -> Any:
        """
        Recursively convert all values to strings (like PHP strval).
        """
        if isinstance(value, dict):
            return {k: HmacPy._to_str_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [HmacPy._to_str_values(v) for v in value]

        # Листовая вершина: имитация strval()
        if value is True:
            return "1"
        if value is False or value is None:
            return ""
        return str(value)

    @staticmethod
    def _sort_recursive(data: Any) -> Any:
        """
        Recursively sort by keys (like PHP ksort + _sort).
        """
        if isinstance(data, dict):
            # ksort по строковому представлению ключей
            return {
                k: HmacPy._sort_recursive(data[k])
                for k in sorted(data.keys(), key=lambda x: str(x))
            }
        if isinstance(data, list):
            return [HmacPy._sort_recursive(v) for v in data]
        return data

    # ---------- JSON ENCODE, МИМИКРИРУЮЩИЙ json_encode(JSON_UNESCAPED_UNICODE) ----------

    @staticmethod
    def _escape_json_string_php(s: str) -> str:
        """Escape JSON string like PHP (including / escaping)."""
        out: List[str] = []
        for ch in s:
            code = ord(ch)
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ch == "/":
                out.append("\\/")  # PHP по умолчанию экранирует /
            elif ch == "\b":
                out.append("\\b")
            elif ch == "\f":
                out.append("\\f")
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif code < 0x20:
                # Прочие управляющие символы -> \u00XX
                out.append("\\u%04x" % code)
            else:
                # Главное отличие от стандартного json.dumps(ensure_ascii=True):
                # unicode-символы оставляем как есть.
                out.append(ch)
        return "".join(out)

    @staticmethod
    def _encode_json_value_php(value: Any) -> str:
        """Encode JSON value like PHP."""
        # после _to_str_values у нас на листьях строки,
        # но оставляем обработку других типов на всякий случай.

        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, (int, float)):
            # в реальности после strval это уже строки,
            # но пусть будет на всякий случай
            return str(value)
        if isinstance(value, str):
            return '"' + HmacPy._escape_json_string_php(value) + '"'
        if isinstance(value, list):
            inner = ",".join(HmacPy._encode_json_value_php(v) for v in value)
            return "[" + inner + "]"
        if isinstance(value, dict):
            # ключи уже отсортированы в _sort_recursive
            items: List[str] = []
            for k, v in value.items():
                key_str = str(k)
                key_json = '"' + HmacPy._escape_json_string_php(key_str) + '"'
                val_json = HmacPy._encode_json_value_php(v)
                items.append(f"{key_json}:{val_json}")
            return "{" + ",".join(items) + "}"

        # fallback — как строка
        return '"' + HmacPy._escape_json_string_php(str(value)) + '"'

    @staticmethod
    def _php_json_encode_unicode(data: JSONType) -> str:
        """Encode to JSON like PHP with JSON_UNESCAPED_UNICODE."""
        return HmacPy._encode_json_value_php(data)
