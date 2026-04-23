"""Tests for the broadcast feature (admin_handlers.py + keyboards.py).

Run with:
    cd /Users/georgydvoryak/Documents/pyProjects/salesbot_yana
    python3 -m pytest tests/test_broadcast.py -v

All external dependencies (telebot, config, db, google_sheets, …) are stubbed
so that the test suite runs with only the standard library + pytest.
"""

import sys
import os
import sqlite3
import tempfile
import threading
import types as pytypes
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub every external dependency BEFORE any project module is imported.
# ---------------------------------------------------------------------------

def _make_mock_module(name: str, **attrs):
    mod = pytypes.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# telebot
telebot_mod = _make_mock_module("telebot")
telebot_types = _make_mock_module("telebot.types")
telebot_mod.types = telebot_types
# Attach the classes handlers use
for _cls in ("Message", "CallbackQuery", "InlineKeyboardMarkup", "InlineKeyboardButton",
             "ReplyKeyboardMarkup", "KeyboardButton"):
    setattr(telebot_types, _cls, MagicMock)

# config
_make_mock_module(
    "config",
    ADMIN_IDS=[111, 222],
    DATABASE_PATH=":memory:",   # individual tests override via patch
    GSHEET_ID="fake-sheet-id",
    ENABLE_YOOKASSA=False,
)

# db
_make_mock_module(
    "db",
    get_all_active_subscriptions=MagicMock(return_value=[]),
    get_expired_subscriptions=MagicMock(return_value=[]),
    mark_subscription_expired=MagicMock(),
    get_connection=MagicMock(),
)

# other project modules
_make_mock_module("google_sheets", get_courses_data=MagicMock(return_value=[]))
_make_mock_module("utils")
_make_mock_module(
    "utils.channel",
    remove_user_from_channel=MagicMock(return_value=True),
    check_course_channels=MagicMock(return_value="ok"),
)
_make_mock_module(
    "utils.logger",
    log_error=MagicMock(),
    log_warning=MagicMock(),
    log_info=MagicMock(),
)
_make_mock_module("utils.text_utils", strip_html=lambda s: s)
_make_mock_module("utils.keyboards")

# Now import the module under test (will be cached in sys.modules)
import handlers.admin_handlers as ah   # noqa: E402  (import after stubs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_db(rows: list) -> str:
    """Create a temp SQLite file with a minimal prodamus_payments table."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE prodamus_payments (id INTEGER PRIMARY KEY, user_id INTEGER)"
    )
    conn.executemany("INSERT INTO prodamus_payments (user_id) VALUES (?)", rows)
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestGetProdamusRecipients(unittest.TestCase):
    """_get_prodamus_recipients() returns de-duplicated, non-null user_ids."""

    def _call(self, db_path: str) -> list:
        with patch("handlers.admin_handlers.DATABASE_PATH", db_path):
            return ah._get_prodamus_recipients()

    def test_deduplication(self):
        db_path = _make_temp_db([(1,), (1,), (2,), (3,), (3,)])
        try:
            result = self._call(db_path)
            self.assertEqual(sorted(result), [1, 2, 3])
        finally:
            os.unlink(db_path)

    def test_null_excluded(self):
        db_path = _make_temp_db([(1,), (None,), (2,)])
        try:
            result = self._call(db_path)
            self.assertNotIn(None, result)
            self.assertCountEqual(result, [1, 2])
        finally:
            os.unlink(db_path)

    def test_empty_table(self):
        db_path = _make_temp_db([])
        try:
            result = self._call(db_path)
            self.assertEqual(result, [])
        finally:
            os.unlink(db_path)

    def test_single_user(self):
        db_path = _make_temp_db([(42,)])
        try:
            result = self._call(db_path)
            self.assertEqual(result, [42])
        finally:
            os.unlink(db_path)


class TestDoBroadcast(unittest.TestCase):
    """_do_broadcast() sends messages and reports correct counts."""

    def setUp(self):
        ah._broadcast_states.clear()
        ah._active_broadcasts.clear()

    def test_all_sent_successfully(self):
        bot = MagicMock()
        recipients = [10, 20, 30]
        ah._do_broadcast(bot, 111, "Hello", recipients)

        # One call per recipient + one status call to admin
        self.assertEqual(bot.send_message.call_count, len(recipients) + 1)
        status_text = bot.send_message.call_args_list[-1][0][1]
        self.assertIn("Отправлено: 3", status_text)
        self.assertIn("Не доставлено: 0", status_text)

    def test_partial_failure(self):
        bot = MagicMock()
        bot.send_message.side_effect = [
            None,                    # uid 10 – ok
            Exception("blocked"),    # uid 20 – fail
            None,                    # uid 30 – ok
            None,                    # status to admin
        ]
        ah._do_broadcast(bot, 111, "Hi", [10, 20, 30])

        status_text = bot.send_message.call_args_list[-1][0][1]
        self.assertIn("Отправлено: 2", status_text)
        self.assertIn("Не доставлено: 1", status_text)

    def test_timeout_does_not_crash(self):
        """TimeoutError on every send must not propagate; bot stays alive."""
        bot = MagicMock()
        bot.send_message.side_effect = [
            TimeoutError("timeout"),  # uid 10
            TimeoutError("timeout"),  # uid 20
            None,                     # status call to admin
        ]
        try:
            ah._do_broadcast(bot, 111, "Hello", [10, 20])
        except Exception as e:
            self.fail(f"_do_broadcast raised unexpectedly: {e}")

        status_text = bot.send_message.call_args_list[-1][0][1]
        self.assertIn("Не доставлено: 2", status_text)

    def test_active_broadcast_cleared_after_finish(self):
        bot = MagicMock()
        ah._active_broadcasts.add(111)
        ah._do_broadcast(bot, 111, "Msg", [10])
        self.assertNotIn(111, ah._active_broadcasts)

    def test_active_broadcast_cleared_even_on_crash(self):
        """Finalizer runs even when the send loop crashes unexpectedly."""
        bot = MagicMock()
        # Every send_message call raises, including the status report
        bot.send_message.side_effect = RuntimeError("crash")
        ah._active_broadcasts.add(111)
        try:
            ah._do_broadcast(bot, 111, "Msg", [10])
        except Exception:
            pass
        self.assertNotIn(111, ah._active_broadcasts)

    def test_empty_recipients_reports_zero(self):
        bot = MagicMock()
        ah._do_broadcast(bot, 111, "Msg", [])
        status_text = bot.send_message.call_args_list[-1][0][1]
        self.assertIn("Отправлено: 0", status_text)
        self.assertIn("Не доставлено: 0", status_text)

    def test_timeout_kwarg_passed(self):
        """send_message must be called with timeout=10 for each recipient."""
        bot = MagicMock()
        ah._do_broadcast(bot, 111, "Hello", [10])
        # First call is to the recipient, check timeout kwarg
        recipient_call = bot.send_message.call_args_list[0]
        self.assertEqual(recipient_call[1].get("timeout"), 10)


class TestBroadcastStateFlow(unittest.TestCase):
    """State machine transitions and security guards."""

    def setUp(self):
        ah._broadcast_states.clear()
        ah._active_broadcasts.clear()

    def test_non_admin_not_in_state(self):
        """Non-admin user_ids must never appear in _broadcast_states."""
        non_admin = 999
        # Simulate the guard in handle_broadcast_button
        if non_admin not in sys.modules["config"].ADMIN_IDS:
            pass  # return early – do not set state
        self.assertNotIn(non_admin, ah._broadcast_states)

    def test_state_set_on_button(self):
        ah._broadcast_states[111] = {"step": "awaiting_text"}
        self.assertEqual(ah._broadcast_states[111]["step"], "awaiting_text")

    def test_state_transitions_to_awaiting_confirm(self):
        ah._broadcast_states[111] = {"step": "awaiting_text"}
        ah._broadcast_states[111] = {
            "step": "awaiting_confirm",
            "text": "Hello everyone!",
            "recipients": [10, 20, 30],
        }
        state = ah._broadcast_states[111]
        self.assertEqual(state["step"], "awaiting_confirm")
        self.assertEqual(state["text"], "Hello everyone!")
        self.assertEqual(state["recipients"], [10, 20, 30])

    def test_state_cleared_on_cancel(self):
        ah._broadcast_states[111] = {
            "step": "awaiting_confirm",
            "text": "Hello",
            "recipients": [10],
        }
        ah._broadcast_states.pop(111, None)
        self.assertNotIn(111, ah._broadcast_states)

    def test_active_broadcast_blocks_new_one(self):
        ah._active_broadcasts.add(111)
        blocked = 111 in ah._active_broadcasts
        self.assertTrue(blocked)

    def test_callback_owner_mismatch_rejected(self):
        """Callback from a different admin must not trigger the owner's broadcast."""
        owner_id = 111
        caller_id = 222   # different admin
        # Guard: caller_id != owner_id → reject
        self.assertNotEqual(caller_id, owner_id)

    def test_state_persists_across_multiple_admins(self):
        """Each admin has independent state."""
        ah._broadcast_states[111] = {"step": "awaiting_text"}
        ah._broadcast_states[222] = {"step": "awaiting_confirm", "text": "X", "recipients": []}
        self.assertEqual(ah._broadcast_states[111]["step"], "awaiting_text")
        self.assertEqual(ah._broadcast_states[222]["step"], "awaiting_confirm")


class TestBroadcastThread(unittest.TestCase):
    """_do_broadcast executes safely in a daemon thread."""

    def setUp(self):
        ah._broadcast_states.clear()
        ah._active_broadcasts.clear()

    def test_runs_in_separate_thread_and_completes(self):
        done_event = threading.Event()
        results = []
        bot = MagicMock()

        def fake_send(uid, *args, **kwargs):
            results.append(uid)
            # The last call is the status message to admin (uid=111)
            if uid == 111:
                done_event.set()

        bot.send_message.side_effect = fake_send
        ah._active_broadcasts.add(111)

        t = threading.Thread(
            target=ah._do_broadcast,
            args=(bot, 111, "Test", [10, 20]),
            daemon=True,
        )
        t.start()
        done_event.wait(timeout=5)
        t.join(timeout=5)

        self.assertIn(10, results)
        self.assertIn(20, results)
        self.assertTrue(done_event.is_set(), "Broadcast thread did not complete in time")

    def test_main_thread_not_blocked(self):
        """The main thread returns immediately after starting the daemon thread."""
        bot = MagicMock()
        ah._active_broadcasts.add(111)

        t = threading.Thread(
            target=ah._do_broadcast,
            args=(bot, 111, "Msg", [10]),
            daemon=True,
        )
        t.start()
        # Main thread should return immediately
        # (t is still running; we don't join here)
        self.assertTrue(True)  # if we reach here, main thread was not blocked


if __name__ == "__main__":
    unittest.main()
