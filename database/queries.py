"""
Read-only query helpers for the profile page.

Pure data functions — no Flask imports. Each helper opens its own
connection via get_db() and closes it before returning.
"""

from datetime import datetime

from database.db import get_db

# Inclusive date bounds; a None bound binds as NULL and is ignored.
_DATE_FILTER = " AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)"


def _date_params(start_date, end_date):
    """Return the bind values for _DATE_FILTER."""
    return (start_date, start_date, end_date, end_date)


def get_user_by_id(user_id):
    """Return a dict with the user's name, email and member_since
    ("Month YYYY" from users.created_at), or None if no such user."""
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None

    try:
        member_since = datetime.strptime(
            row["created_at"][:10], "%Y-%m-%d"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = ""

    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


# ------------------------------------------------------------------ #
# Transaction history                                                 #
# ------------------------------------------------------------------ #

def get_recent_transactions(user_id, limit=10, *, start_date=None,
                            end_date=None):
    """Return up to `limit` of the user's expenses, newest first,
    optionally limited to an inclusive start_date/end_date range."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, date, description, category, amount FROM expenses "
        "WHERE user_id = ?" + _DATE_FILTER
        + " ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, *_date_params(start_date, end_date), limit),
    ).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# ------------------------------------------------------------------ #
# Summary stats                                                       #
# ------------------------------------------------------------------ #

def get_summary_stats(user_id, *, start_date=None, end_date=None):
    """Return total_spent, transaction_count and top_category, optionally
    limited to an inclusive start_date/end_date range.
    With no expenses, returns zeros and "—" as the top category."""
    params = (user_id, *_date_params(start_date, end_date))
    conn = get_db()
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?" + _DATE_FILTER,
        params,
    ).fetchone()
    top = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ?" + _DATE_FILTER
        + " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
        params,
    ).fetchone()
    conn.close()

    if totals["count"] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": round(float(totals["total"]), 2),
        "transaction_count": totals["count"],
        "top_category": top["category"],
    }


# ------------------------------------------------------------------ #
# Category breakdown                                                  #
# ------------------------------------------------------------------ #

def get_category_breakdown(user_id, *, start_date=None, end_date=None):
    """Return per-category name, amount and pct, largest first, optionally
    limited to an inclusive start_date/end_date range.

    pct values are integers that sum to exactly 100; any rounding
    remainder is absorbed by the largest category. Returns [] when the
    user has no expenses."""
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS amount FROM expenses "
        "WHERE user_id = ?" + _DATE_FILTER
        + " GROUP BY category ORDER BY amount DESC",
        (user_id, *_date_params(start_date, end_date)),
    ).fetchall()
    conn.close()
    if not rows:
        return []

    total = sum(row["amount"] for row in rows)
    categories = [
        {
            "name": row["category"],
            "amount": round(float(row["amount"]), 2),
            "pct": round(row["amount"] / total * 100) if total else 0,
        }
        for row in rows
    ]
    if total:
        categories[0]["pct"] += 100 - sum(c["pct"] for c in categories)
    return categories
