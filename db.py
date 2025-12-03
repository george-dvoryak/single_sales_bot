# db.py
import sqlite3
import time

from config import DATABASE_PATH

_conn = None

def get_connection():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _conn.execute("PRAGMA foreign_keys = ON;")
        _conn.row_factory = sqlite3.Row
        init_db(_conn)
    return _conn

def init_db(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id TEXT,
            course_name TEXT,
            channel_id TEXT,
            expiry INTEGER,    -- UNIX timestamp (UTC)
            payment_id TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prodamus_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            user_id INTEGER,
            course_id TEXT,
            customer_email TEXT,
            payment_url TEXT,
            payment_status TEXT,
            order_num TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """
    )
    conn.commit()

def add_user(user_id: int, username: str = None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?);", (user_id, username))
    except sqlite3.IntegrityError:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?;", (username, user_id))
    conn.commit()

def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,))
    return cur.fetchone()

def add_purchase(user_id: int, course_id: str, course_name: str, channel_id: str, duration_days: int, payment_id: str = None):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())

    # duration_days > 0 → limited-time access
    # duration_days <= 0 or None → practically unlimited access (set very far future expiry)
    try:
        d = int(duration_days) if duration_days is not None else 0
    except (ValueError, TypeError):
        d = 0

    if d > 0:
        expiry_ts = now + d * 24 * 60 * 60  # days → seconds
    else:
        # Unlimited courses: set expiry to 50 years from now
        expiry_ts = now + 50 * 365 * 24 * 60 * 60
    cur.execute(
        """
        INSERT INTO purchases (user_id, course_id, course_name, channel_id, expiry, payment_id)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (user_id, course_id, course_name, channel_id, expiry_ts, payment_id)
    )
    conn.commit()
    return expiry_ts

def get_active_subscriptions(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT course_name, channel_id, expiry FROM purchases
        WHERE user_id = ? AND expiry > ?;
        """,
        (user_id, now)
    )
    return cur.fetchall()

def has_active_subscription(user_id: int, course_id: str):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT 1 FROM purchases WHERE user_id = ? AND course_id = ? AND expiry > ?;
        """,
        (user_id, course_id, now)
    )
    return cur.fetchone() is not None

def mark_subscription_expired(user_id: int, course_id: str):
    """
    Mark subscription as expired by setting expiry to 0 (processed flag).
    Using 0 instead of current time to distinguish processed from unprocessed expired subscriptions.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE purchases SET expiry = 0
        WHERE user_id = ? AND course_id = ?;
        """,
        (user_id, course_id)
    )
    conn.commit()

def get_expired_subscriptions():
    """
    Get subscriptions that have expired but haven't been processed yet.
    Only returns subscriptions where expiry > 0 (not yet marked as processed).
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT user_id, course_id, course_name, channel_id, expiry
        FROM purchases
        WHERE expiry > 0 AND expiry <= ?
        ORDER BY expiry ASC;
        """,
        (now,)
    )
    return cur.fetchall()

def get_all_active_subscriptions():
    """Get all active subscriptions for all users (admin function)"""
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT user_id, course_id, course_name, channel_id, expiry
        FROM purchases
        WHERE expiry > ?
        ORDER BY expiry DESC;
        """,
        (now,)
    )
    return cur.fetchall()


# Prodamus payment tracking functions
def create_prodamus_payment(order_id: str, user_id: int, course_id: str, customer_email: str, order_num: str):
    """Create a new Prodamus payment record"""
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    try:
        cur.execute(
            """
            INSERT INTO prodamus_payments (order_id, user_id, course_id, customer_email, order_num, payment_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?);
            """,
            (order_id, user_id, course_id, customer_email, order_num, now, now)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Order ID already exists
        return False


def update_prodamus_payment_url(order_id: str, payment_url: str):
    """Update payment URL for a Prodamus payment"""
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        UPDATE prodamus_payments 
        SET payment_url = ?, updated_at = ?
        WHERE order_id = ?;
        """,
        (payment_url, now, order_id)
    )
    conn.commit()


def update_prodamus_payment_status(order_id: str, payment_status: str):
    """Update payment status for a Prodamus payment"""
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        UPDATE prodamus_payments 
        SET payment_status = ?, updated_at = ?
        WHERE order_id = ?;
        """,
        (payment_status, now, order_id)
    )
    conn.commit()


def get_prodamus_payment(order_id: str):
    """Get Prodamus payment by order_id"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM prodamus_payments WHERE order_id = ?;
        """,
        (order_id,)
    )
    return cur.fetchone()


def get_prodamus_payment_by_order_num(order_num: str):
    """Get Prodamus payment by order_num"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM prodamus_payments WHERE order_num = ?;
        """,
        (order_num,)
    )
    return cur.fetchone()
