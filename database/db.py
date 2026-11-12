import os
import random
import sqlite3
from datetime import date

from werkzeug.security import check_password_hash, generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "expense_tracker.db")

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    """Return a SQLite connection with dict-like rows and foreign keys enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist. Safe to call repeatedly."""
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_user(name, email, password):
    """Insert a new user with a hashed password and return its id.

    Raises sqlite3.IntegrityError if the email is already registered.
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def authenticate_user(email, password):
    """Return the user's id if the email/password pair is valid, else None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return row["id"]
    return None


def get_user_by_id(user_id):
    """Return the user's public fields (no password hash), or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_expense_summary(user_id):
    """Return total spent, expense count and top category for a user."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_amount, "
            "COUNT(*) AS expense_count, "
            "COUNT(DISTINCT strftime('%Y-%m', date)) AS active_months "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return {
            "total_amount": float(totals["total_amount"]),
            "expense_count": int(totals["expense_count"]),
            "active_months": int(totals["active_months"]),
            "top_category": top["category"] if top else None,
        }
    finally:
        conn.close()


def get_category_breakdown(user_id):
    """Return (category, total, count) rows for a user, largest total first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS count "
            "FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=5):
    """Return a user's most recent expenses, newest first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()


def get_monthly_totals(user_id, since):
    """Return {'YYYY-MM': total} for a user's expenses dated on/after `since`."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? AND date >= ? "
            "GROUP BY month ORDER BY month",
            (user_id, since),
        ).fetchall()
        return {row["month"]: row["total"] for row in rows}
    finally:
        conn.close()


def get_largest_expenses(user_id, limit=3):
    """Return a user's biggest expenses, one per description, largest first.

    Grouping by description stops a recurring cost (e.g. rent) filling the list.
    SQLite returns the other columns from the row holding MAX(amount).
    """
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, MAX(amount) AS amount, category, date, description "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY COALESCE(description, category) "
            "ORDER BY amount DESC, date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()


# Static demo data: (category, description, min ₹, max ₹, times per month)
_DEMO_PATTERNS = [
    ("Food", "Groceries — BigBasket", 900, 2200, 3),
    ("Food", "Swiggy dinner", 250, 750, 4),
    ("Food", "Coffee with team", 120, 380, 2),
    ("Transport", "Uber to office", 180, 520, 4),
    ("Transport", "Metro card recharge", 500, 500, 1),
    ("Transport", "Petrol", 1500, 2800, 1),
    ("Bills", "Electricity bill", 1400, 2600, 1),
    ("Bills", "Mobile + broadband", 1199, 1199, 1),
    ("Bills", "House rent", 18000, 18000, 1),
    ("Health", "Pharmacy", 200, 900, 1),
    ("Health", "Gym membership", 1500, 1500, 1),
    ("Entertainment", "Netflix subscription", 649, 649, 1),
    ("Entertainment", "Movie night", 400, 1100, 1),
    ("Shopping", "Amazon order", 600, 4500, 2),
    ("Other", "Gift / misc", 300, 1500, 1),
]


def seed_demo_expenses(name, email, password, months=6, seed=42):
    """Give a demo user `months` months of realistic expenses.

    Creates the user if missing (existing passwords are left alone) and does
    nothing if the user already has expenses. A fixed RNG seed keeps the data
    identical between runs; dates are anchored to the current month.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row:
            user_id = row["id"]
        else:
            user_id = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            ).lastrowid

        has_expenses = conn.execute(
            "SELECT 1 FROM expenses WHERE user_id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if has_expenses:
            conn.commit()
            return

        rng = random.Random(seed)
        today = date.today()
        rows = []
        for back in range(months - 1, -1, -1):
            y, m = today.year, today.month - back
            while m < 1:
                y, m = y - 1, m + 12
            last_day = 28 if back else today.day
            for category, desc, lo, hi, times in _DEMO_PATTERNS:
                for _ in range(times):
                    # Skip some items for month-to-month variety
                    if times > 1 and rng.random() < 0.25:
                        continue
                    # Current month is only partly over
                    if back == 0 and rng.random() > today.day / 30:
                        continue
                    day = rng.randint(1, last_day)
                    amount = round(rng.uniform(lo, hi) / 10) * 10 if lo != hi else lo
                    rows.append(
                        (user_id, float(amount), category,
                         date(y, m, day).isoformat(), desc)
                    )
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert a demo user and sample expenses once. No-op if users already exist."""
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid

        today = date.today()
        samples = [
            (1, 12.50, "Food", "Lunch at cafe"),
            (3, 45.00, "Transport", "Monthly metro pass top-up"),
            (5, 120.00, "Bills", "Electricity bill"),
            (8, 60.00, "Health", "Pharmacy"),
            (11, 25.00, "Entertainment", "Movie tickets"),
            (14, 89.99, "Shopping", "New shoes"),
            (18, 15.00, "Other", "Miscellaneous"),
            (22, 32.75, "Food", "Groceries"),
        ]
        rows = [
            (user_id, amount, category, today.replace(day=day).isoformat(), desc)
            for day, amount, category, desc in samples
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
