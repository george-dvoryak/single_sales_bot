import hmac
import hashlib
import json
from typing import Any, Dict, List, Union

JSONType = Union[Dict[str, Any], List[Any]]


class ProdamusHmac:
    """
    Эквивалент PHP-класса Hmac:

        static function create($data, $key, $algo = 'sha256')
        static function verify($data, $key, $sign, $algo = 'sha256')

    Логика:
      - (array)$data
      - array_walk_recursive + strval
      - рекурсивный ksort
      - json_encode(..., JSON_UNESCAPED_UNICODE)
      - hash_hmac($algo, $json, $key)
    """

    # ---------- Публичные методы ----------

    @staticmethod
    def create(data: Any, key: str, algo: str = "sha256") -> str | None:
        digestmod = ProdamusHmac._get_digestmod(algo)
        if digestmod is None:
            return None  # как false в PHP

        array_data = ProdamusHmac._php_array_cast(data)
        array_data = ProdamusHmac._to_str_values(array_data)
        array_data = ProdamusHmac._sort_recursive(array_data)

        json_str = ProdamusHmac._php_json_encode_unicode(array_data)

        mac = hmac.new(key.encode("utf-8"), json_str.encode("utf-8"), digestmod)
        return mac.hexdigest()

    @staticmethod
    def verify(data: Any, key: str, sign: str, algo: str = "sha256") -> bool:
        calc = ProdamusHmac.create(data, key, algo)
        if not calc:
            return False
        return hmac.compare_digest(calc.lower(), str(sign).lower())

    # ---------- Внутренние хелперы ----------

    @staticmethod
    def _get_digestmod(algo: str):
        try:
            return getattr(hashlib, algo)
        except AttributeError:
            return None

    @staticmethod
    def _php_array_cast(data: Any) -> JSONType:
        """
        Имитация (array)$data + поддержка JSON-строки.

        Если data — str и похоже на JSON ({ или [), пробуем json.loads().
        Это как раз твой случай, когда ты вставляешь длинную JSON-строку.
        """
        if isinstance(data, str):
            stripped = data.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(data)
                    return ProdamusHmac._php_array_cast(parsed)
                except Exception:
                    return [data]
            return [data]

        if isinstance(data, dict):
            return dict(data)

        if isinstance(data, list):
            return list(data)

        # скаляр -> [скаляр]
        return [data]

    @staticmethod
    def _to_str_values(value: Any) -> Any:
        """
        Аналог array_walk_recursive + strval.
        Все конечные значения становятся строками.
        """
        if isinstance(value, dict):
            return {k: ProdamusHmac._to_str_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ProdamusHmac._to_str_values(v) for v in value]

        if value is True:
            return "1"
        if value is False or value is None:
            return ""
        return str(value)

    @staticmethod
    def _sort_recursive(data: Any) -> Any:
        """
        Аналог приватного _sort(&$data) в PHP:
            ksort($data, SORT_REGULAR);
            foreach ($data as &$arr)
                is_array($arr) && self::_sort($arr);
        """
        if isinstance(data, dict):
            return {
                k: ProdamusHmac._sort_recursive(data[k])
                for k in sorted(data.keys(), key=lambda x: str(x))
            }
        if isinstance(data, list):
            return [ProdamusHmac._sort_recursive(v) for v in data]
        return data

    # --- JSON-энкодер в стиле json_encode(JSON_UNESCAPED_UNICODE) ---

    @staticmethod
    def _escape_json_string_php(s: str) -> str:
        """
        Экранирование строки примерно как у PHP json_encode:
        - Unicode не экранируем (\uXXXX) (UNESCAPED_UNICODE)
        - Но экранируем ", \, / и управляющие символы.
        """
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
            return '"' + ProdamusHmac._escape_json_string_php(value) + '"'
        if isinstance(value, list):
            inner = ",".join(ProdamusHmac._encode_json_value_php(v) for v in value)
            return "[" + inner + "]"
        if isinstance(value, dict):
            items: List[str] = []
            for k, v in value.items():
                key_str = str(k)
                key_json = '"' + ProdamusHmac._escape_json_string_php(key_str) + '"'
                val_json = ProdamusHmac._encode_json_value_php(v)
                items.append(f"{key_json}:{val_json}")
            return "{" + ",".join(items) + "}"

        return '"' + ProdamusHmac._escape_json_string_php(str(value)) + '"'

    @staticmethod
    def _php_json_encode_unicode(data: JSONType) -> str:
        return ProdamusHmac._encode_json_value_php(data)