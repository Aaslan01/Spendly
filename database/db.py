import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_PATH = "expense_tracker.db"


def get_db():
    """
    Opens a connection to the SQLite database and returns it.
    Sets row_factory for dict-like access and enables foreign keys.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Creates the users and expenses tables if they don't exist.
    Safe to call multiple times.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def create_user(name, email, password):
    """
    Creates a new user with the given name, email, and password.
    Hashes the password using werkzeug before storing.
    Returns the new user's ID.
    Raises sqlite3.IntegrityError if email is already registered.
    """
    conn = get_db()
    cursor = conn.cursor()

    password_hash = generate_password_hash(password)

    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash)
    )

    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return user_id


def seed_db():
    """
    Inserts sample data for development.
    Only runs once - checks for existing data before inserting.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Check if users table already has data
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Insert demo user
    password_hash = generate_password_hash("demo123")
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash)
    )

    # Get the user ID
    cursor.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",))
    user_id = cursor.fetchone()[0]

    # Insert 8 sample expenses across different categories
    sample_expenses = [
        (15.50, "Food", "2026-04-01", "Lunch at cafe"),
        (45.00, "Transport", "2026-04-03", "Uber rides"),
        (120.00, "Bills", "2026-04-05", "Electric bill"),
        (35.00, "Health", "2026-04-07", "Pharmacy"),
        (60.00, "Entertainment", "2026-04-10", "Movie tickets and dinner"),
        (200.00, "Shopping", "2026-04-12", "New shoes"),
        (25.00, "Other", "2026-04-14", "Miscellaneous"),
        (55.00, "Food", "2026-04-15", "Grocery shopping"),
    ]

    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, amount, category, date, desc) for amount, category, date, desc in sample_expenses]
    )

    conn.commit()
    conn.close()
