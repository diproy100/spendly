"""Pure query helpers for the profile page (no Flask imports).

Each helper opens its own connection through get_db() and closes it before
returning. All queries are parameterised and scoped by user_id.
"""

from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return {'name', 'email', 'member_since'} or None if the user is missing."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = None
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


def get_summary_stats(user_id):
    """Return {'total_spent', 'transaction_count', 'top_category'}."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": round(float(totals["total"]), 2),
        "transaction_count": int(totals["n"]),
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=10):
    """Return the user's newest expenses as a list of dicts."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": r["date"],
            "description": r["description"],
            "category": r["category"],
            "amount": r["amount"],
        }
        for r in rows
    ]


def get_category_breakdown(user_id):
    """Return [{'name', 'amount', 'pct'}] largest first.

    pct values are integers that sum to 100; the largest category absorbs
    any rounding remainder. Empty list when the user has no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS amount FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY amount DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    total = sum(r["amount"] for r in rows)
    if not rows or total <= 0:
        return []
    result = [
        {
            "name": r["category"],
            "amount": r["amount"],
            "pct": round(r["amount"] / total * 100),
        }
        for r in rows
    ]
    result[0]["pct"] += 100 - sum(c["pct"] for c in result)
    return result
