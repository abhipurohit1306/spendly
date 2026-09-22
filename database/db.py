"""
Database access layer for Spendly.

Provides connection management, schema creation, and demo data seeding.
All SQL for the app lives here — routes must call these functions rather
than touching sqlite3 directly.
"""

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"


def get_db():
    """Open a new SQLite connection with row access by column name and
    foreign key enforcement enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and expenses tables if they do not already exist."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    """Insert one demo user and 8 sample expenses, but only if the users
    table is currently empty (safe to call on every startup)."""
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    sample_expenses = [
        (user_id, 12.50, "Food", "2026-09-02", "Coffee and bagel"),
        (user_id, 45.00, "Transport", "2026-09-04", "Monthly metro pass"),
        (user_id, 89.99, "Bills", "2026-09-05", "Electricity bill"),
        (user_id, 25.00, "Health", "2026-09-09", "Pharmacy - vitamins"),
        (user_id, 32.75, "Food", "2026-09-11", "Groceries"),
        (user_id, 15.00, "Entertainment", "2026-09-14", "Movie ticket"),
        (user_id, 60.20, "Shopping", "2026-09-17", "New running shoes"),
        (user_id, 20.00, "Other", "2026-09-20", "Birthday gift"),
    ]
    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        sample_expenses,
    )

    conn.commit()
    conn.close()
