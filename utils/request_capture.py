"""Persistent capture of incoming webhook requests (delivery diagnostics).

Server logs on PythonAnywhere rotate and are hard to read from outside, so every
hit on the Prodamus endpoint (and every 404/405 miss) is also appended here as one
JSON object per line. Reading is exposed via the authenticated /prodamus_log route.
"""

import json
import os
import time

from flask import request

from config import REQUEST_CAPTURE_LOG
from utils.logger import log_info, log_warning

# Keep the file small; when exceeded it is rotated to <name>.1 (previous .1 dropped)
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_BODY_CHARS = 20000


def _mask_path(path: str) -> str:
    """Hide long path segments (the Telegram webhook path carries the bot token)."""
    parts = []
    for part in path.split("/"):
        parts.append(f"{part[:6]}…{part[-4:]}" if len(part) > 30 else part)
    return "/".join(parts)


def _rotate_if_needed() -> None:
    try:
        if os.path.exists(REQUEST_CAPTURE_LOG) and os.path.getsize(REQUEST_CAPTURE_LOG) > MAX_LOG_BYTES:
            os.replace(REQUEST_CAPTURE_LOG, REQUEST_CAPTURE_LOG + ".1")
    except Exception as e:
        log_warning("request_capture", f"Could not rotate capture log: {e}")


def _append(entry: dict) -> None:
    try:
        _rotate_if_needed()
        with open(REQUEST_CAPTURE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log_warning("request_capture", f"Could not write capture log: {e}")


def _base_entry(tag: str) -> dict:
    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC",
        "tag": tag,
        "method": request.method,
        "path": _mask_path(request.path),
        "query": request.query_string.decode("utf-8", errors="replace")[:500],
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr or ""),
        "user_agent": request.headers.get("User-Agent", "")[:300],
    }


def capture_full_request(tag: str) -> None:
    """Capture method, path, all headers and the raw body.

    Safe to call before request.form is used: get_data(cache=True) keeps the body
    buffered, so Werkzeug can still parse urlencoded and multipart afterwards.
    """
    entry = _base_entry(tag)
    try:
        raw = request.get_data(cache=True, as_text=False)
        entry["content_type"] = request.content_type or ""
        entry["body_bytes"] = len(raw)
        entry["headers"] = {k: v for k, v in request.headers.items()}
        entry["body"] = raw.decode("utf-8", errors="replace")[:MAX_BODY_CHARS]
    except Exception as e:
        entry["capture_error"] = str(e)
    _append(entry)
    log_info(
        "request_capture",
        f"{tag}: {entry['method']} {entry['path']} from {entry['ip']} "
        f"({entry.get('body_bytes', '?')} bytes, UA={entry['user_agent'][:60]!r})",
    )


def capture_miss(tag: str) -> None:
    """Capture a request that matched no route (404) or no method (405). No body."""
    entry = _base_entry(tag)
    _append(entry)
    log_warning(
        "request_capture",
        f"{tag}: {entry['method']} {entry['path']} from {entry['ip']} "
        f"UA={entry['user_agent'][:60]!r} — маршрут не найден",
    )


def read_captures(limit: int = 20, contains: str = None) -> list:
    """Return the last `limit` captured entries, newest last.

    `contains` keeps only entries whose raw line holds that substring
    (case-insensitive) — the endpoint is public, so unrelated 404s from internet
    scanners land here too and would otherwise crowd out what we are looking for.
    """
    lines = []
    for path in (REQUEST_CAPTURE_LOG + ".1", REQUEST_CAPTURE_LOG):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    lines.extend(f.readlines())
        except Exception as e:
            log_warning("request_capture", f"Could not read {path}: {e}")

    if contains:
        needle = contains.lower()
        lines = [line for line in lines if needle in line.lower()]

    entries = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            entries.append({"raw_line": line[:500]})
    return entries
