"""
Reusable query helpers for the /profile route.
All functions use parameterized queries and return plain dicts (not sqlite3.Row).
"""
import sqlite3
from datetime import datetime

from database.db import get_db

# 7 bar-width CSS classes ordered widest → narrowest (matches rank by spend).
# profile.css only defines exactly these 7 classes — do not change this list.
_BAR_CLASSES = [
    "bar-w-68", "bar-w-50", "bar-w-36", "bar-w-25",
    "bar-w-10", "bar-w-06", "bar-w-03",
]


def _date_where(user_id, date_from, date_to):
    """Return (where_clause, params) for filtering expenses by user and optional date range."""
    where = "WHERE user_id = ?"
    params = [user_id]
    if date_from and date_to:
        where += " AND date BETWEEN ? AND ?"
        params.extend([date_from, date_to])
    elif date_from:
        where += " AND date >= ?"
        params.append(date_from)
    elif date_to:
        where += " AND date <= ?"
        params.append(date_to)
    return where, params


# ── AGENT 2 BEGIN (User Info + Stats) ────────────────────────────── #

def get_user_by_id(user_id):
    """Return {name, email, initials, member_since} for the given user, or None."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if row is None:
            return None
        name = row["name"]
        words = name.split()
        initials = "".join(w[0].upper() for w in words[:2])
        created_at = row["created_at"]
        try:
            member_since = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
        except ValueError:
            member_since = datetime.strptime(created_at, "%Y-%m-%d").strftime("%B %Y")
        return {
            "name": name,
            "email": row["email"],
            "initials": initials,
            "member_since": member_since,
        }
    finally:
        db.close()


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {total_spent, transaction_count, top_category}."""
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS tx_count"
            " FROM expenses " + where,
            params
        ).fetchone()
        total = row["total"]
        tx_count = row["tx_count"]
        cat_row = db.execute(
            "SELECT category FROM expenses " + where +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            params
        ).fetchone()
        top_category = cat_row["category"] if cat_row else "—"
        return {
            "total_spent": f"{total:,.2f}",
            "transaction_count": tx_count,
            "top_category": top_category,
        }
    finally:
        db.close()

# ── AGENT 2 END ──────────────────────────────────────────────────── #


# ── AGENT 1 BEGIN (Transaction History) ──────────────────────────── #

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return up to `limit` expenses newest-first as list of dicts."""
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)
        rows = db.execute(
            "SELECT date, description, category, amount"
            " FROM expenses "
            + where +
            " ORDER BY date DESC, id DESC"
            " LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [
            {
                "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y"),
                "description": r["description"],
                "category": r["category"],
                "amount": f"{r['amount']:,.2f}",
            }
            for r in rows
        ]
    finally:
        db.close()

# ── AGENT 1 END ──────────────────────────────────────────────────── #


# ── AGENT 3 BEGIN (Category Breakdown) ───────────────────────────── #

def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return per-category totals with pct and bar_class, ordered by amount DESC."""
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)
        rows = db.execute(
            "SELECT category, SUM(amount) AS total"
            " FROM expenses "
            + where +
            " GROUP BY category"
            " ORDER BY total DESC",
            params,
        ).fetchall()

        grand_total = sum(r["total"] for r in rows)
        if grand_total == 0:
            return []

        result = []
        for rank, row in enumerate(rows):
            amt = row["total"]
            name = row["category"]
            bar_class = _BAR_CLASSES[rank] if rank < len(_BAR_CLASSES) else _BAR_CLASSES[-1]
            result.append({
                "name": name,
                "slug": name.lower(),
                "amount": f"{amt:,.2f}",
                "pct": round(amt / grand_total * 100),
                "bar_class": bar_class,
            })
        return result
    finally:
        db.close()

# ── AGENT 3 END ──────────────────────────────────────────────────── #


def insert_expense(user_id, amount, category, date, description):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()
