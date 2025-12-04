# db.py
"""Database operations for the bot."""

import sqlite3
import time

from config import DATABASE_PATH
from utils.logger import log_error, log_warning

_conn = None

def get_connection():
    """
    Get or create database connection (singleton pattern).
    
    Returns:
        sqlite3.Connection: Database connection
    """
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _conn.execute("PRAGMA foreign_keys = ON;")
        _conn.row_factory = sqlite3.Row
        init_db(_conn)
    return _conn


def init_db(conn):
    """
    Initialize database tables if they don't exist.
    
    Args:
        conn: sqlite3.Connection object
    """
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_email (
            tg_id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            FOREIGN KEY(tg_id) REFERENCES users(user_id)
        )
        """
    )
    conn.commit()

def add_user(user_id: int, username: str = None):
    """
    Add or update a user in the database.
    
    Args:
        user_id: Telegram user ID
        username: Telegram username (optional)
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?);", (user_id, username))
    except sqlite3.IntegrityError:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?;", (username, user_id))
    conn.commit()

def get_user(user_id: int):
    """
    Get user by ID.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        sqlite3.Row or None: User record if found
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,))
    return cur.fetchone()

def add_purchase(user_id: int, course_id: str, course_name: str, channel_id: str, duration_days: int, payment_id: str = None):
    """
    Add a purchase record (grant course access).
    
    Args:
        user_id: Telegram user ID
        course_id: Course ID
        course_name: Course name
        channel_id: Telegram channel ID or username
        duration_days: Access duration in days (0 or negative = unlimited)
        payment_id: Payment transaction ID (optional)
        
    Returns:
        int: Expiry timestamp (UNIX timestamp)
    """
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
    """
    Get all active subscriptions for a user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        List of subscription records (sqlite3.Row objects)
    """
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
    """
    Check if user has an active subscription to a course.
    
    Args:
        user_id: Telegram user ID
        course_id: Course ID
        
    Returns:
        bool: True if user has active subscription
    """
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
    
    Args:
        user_id: Telegram user ID
        course_id: Course ID
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
    
    Returns:
        List of expired subscription records (sqlite3.Row objects)
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
    """
    Get all active subscriptions for all users (admin function).
    
    Returns:
        List of active subscription records (sqlite3.Row objects)
    """
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
    """
    Create a new Prodamus payment record.
    
    Args:
        order_id: Order ID (unique identifier)
        user_id: Telegram user ID
        course_id: Course ID
        customer_email: Customer email address
        order_num: Order number (format: user_id_course_id_timestamp)
        
    Returns:
        bool: True if created successfully, False if duplicate or error
    """
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
    except sqlite3.OperationalError as e:
        # Database is locked or other operational issue – let caller retry or fail gracefully
        log_warning("db", f"create_prodamus_payment OperationalError: {e}")
        time.sleep(0.1)
        return False


def update_prodamus_payment_url(order_id: str, payment_url: str):
    """
    Update payment URL for a Prodamus payment.
    
    Args:
        order_id: Order ID
        payment_url: Payment URL from Prodamus
    """
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
    """
    Update payment status for a Prodamus payment.
    
    Args:
        order_id: Order ID or order_num
        payment_status: Payment status (e.g., "success", "pending", "failed")
    """
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
    """
    Get Prodamus payment by order_id.
    
    Args:
        order_id: Order ID
        
    Returns:
        sqlite3.Row or None: Payment record if found
    """
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
    """
    Get Prodamus payment by order_num.
    
    Args:
        order_num: Order number (format: user_id_course_id_timestamp)
        
    Returns:
        sqlite3.Row or None: Payment record if found
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM prodamus_payments WHERE order_num = ?;
        """,
        (order_num,)
    )
    return cur.fetchone()


def get_user_email(user_id: int) -> str | None:
    """
    Get user email from database.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        str or None: Email address if found, None otherwise
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT email FROM user_email WHERE tg_id = ?;", (user_id,))
    row = cur.fetchone()
    return row["email"] if row else None


def set_user_email(user_id: int, email: str) -> bool:
    """
    Set or update user email in database.
    
    Args:
        user_id: Telegram user ID
        email: Email address
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Ensure user exists in users table (required for foreign key constraint)
        # Use the same pattern as add_user function
        try:
            cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?);", (user_id, None))
        except sqlite3.IntegrityError:
            # User already exists, that's fine
            pass
        
        # Insert or update email using INSERT OR REPLACE (SQLite compatible)
        cur.execute(
            "INSERT OR REPLACE INTO user_email (tg_id, email) VALUES (?, ?);",
            (user_id, email)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        # Foreign key constraint violation - user doesn't exist and insert failed
        log_error("db", f"Foreign key constraint violation setting user email for user {user_id}: {e}")
        # Try to add user explicitly and retry
        try:
            add_user(user_id, None)
            cur.execute(
                "INSERT OR REPLACE INTO user_email (tg_id, email) VALUES (?, ?);",
                (user_id, email)
            )
            conn.commit()
            return True
        except Exception as retry_e:
            log_error("db", f"Error retrying set_user_email after adding user: {retry_e}", exc_info=True)
            return False
    except Exception as e:
        log_error("db", f"Error setting user email: {e}", exc_info=True)
        return False
