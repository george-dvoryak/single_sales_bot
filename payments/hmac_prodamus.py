# hmac_prodamus.py
import hmac
import hashlib
import json
from typing import Any, Dict, List, Union

JSONType = Union[Dict[str, Any], List[Any]]


class HmacPy:
    @staticmethod
    def create(data: Any, key: str, algo: str = "sha256") -> str | None:
        digestmod = HmacPy._get_digestmod(algo)
        if digestmod is None:
            return None

        array_data = HmacPy._php_array_cast(data)
        array_data = HmacPy._to_str_values(array_data)
        array_data = HmacPy._sort_recursive(array_data)
        json_str = HmacPy._php_json_encode_unicode(array_data)

        mac = hmac.new(key.encode("utf-8"), json_str.encode("utf-8"), digestmod)
        return mac.hexdigest()

    @staticmethod
    def verify(data: Any, key: str, sign: str, algo: str = "sha256") -> bool:
        calc = HmacPy.create(data, key, algo)
        if not calc:
            return False
        return hmac.compare_digest(calc.lower(), str(sign).lower())

    # ----------- дальше всё как в твоём коде -----------

    @staticmethod
    def _get_digestmod(algo: str):
        try:
            return getattr(hashlib, algo)
        except AttributeError:
            return None

    @staticmethod
    def _php_array_cast(data: Any) -> JSONType:
        if isinstance(data, str):
            stripped = data.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(data)
                    return HmacPy._php_array_cast(parsed)
                except Exception:
                    return [data]
            return [data]

        if isinstance(data, dict):
            return dict(data)
        if isinstance(data, list):
            return list(data)
        return [data]

    @staticmethod
    def _to_str_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: HmacPy._to_str_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [HmacPy._to_str_values(v) for v in value]
        if value is True:
            return "1"
        if value is False or value is None:
            return ""
        return str(value)

    @staticmethod
    def _sort_recursive(data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: HmacPy._sort_recursive(data[k])
                for k in sorted(data.keys(), key=lambda x: str(x))
            }
        if isinstance(data, list):
            return [HmacPy._sort_recursive(v) for v in data]
        return data

    @staticmethod
    def _escape_json_string_php(s: str) -> str:
        out: List[str] = []
        for ch in s:
            code = ord(ch)
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ch == "/":
                out.append("\\/")  # как у PHP
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
                out.append("\\u%04x" % code)
            else:
                out.append(ch)
        return "".join(out)

    @staticmethod
    def _encode_json_value_php(value: Any) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return '"' + HmacPy._escape_json_string_php(value) + '"'
        if isinstance(value, list):
            inner = ",".join(HmacPy._encode_json_value_php(v) for v in value)
            return "[" + inner + "]"
        if isinstance(value, dict):
            items: List[str] = []
            for k, v in value.items():
                key_str = str(k)
                key_json = '"' + HmacPy._escape_json_string_php(key_str) + '"'
                val_json = HmacPy._encode_json_value_php(v)
                items.append(f"{key_json}:{val_json}")
            return "{" + ",".join(items) + "}"
        return '"' + HmacPy._escape_json_string_php(str(value)) + '"'

    @staticmethod
    def _php_json_encode_unicode(data: JSONType) -> str:
        return HmacPy._encode_json_value_php(data)