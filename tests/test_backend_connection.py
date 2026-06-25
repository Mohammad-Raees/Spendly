"""
Tests for database/queries.py and the /profile route.

Seed data (demo@spendly.com / demo123) — 8 expenses, current month:
  day 2  Food         12.50  Groceries at local market
  day 4  Transport    45.00  Monthly bus pass
  day 5  Bills        89.99  Electricity bill
  day 9  Health       15.00  Pharmacy - pain relief
  day 12 Entertainment 30.00 Movie tickets
  day 15 Shopping     60.25  New pair of shoes
  day 18 Food          8.75  Coffee and lunch
  day 21 Other        20.00  Miscellaneous donation

Total: 281.49  |  Top category: Bills (89.99)
Newest: day 21 Other  |  Oldest: day 2 Food
"""

import re

import pytest

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

_VALID_BAR_CLASSES = {
    "bar-w-68", "bar-w-50", "bar-w-36", "bar-w-25",
    "bar-w-10", "bar-w-06", "bar-w-03",
}


# ── get_user_by_id ────────────────────────────────────────────────── #

class TestGetUserById:
    def test_returns_name(self, app, seeded_user_id):
        with app.app_context():
            result = get_user_by_id(seeded_user_id)
        assert result["name"] == "Demo User"

    def test_returns_email(self, app, seeded_user_id):
        with app.app_context():
            result = get_user_by_id(seeded_user_id)
        assert result["email"] == "demo@spendly.com"

    def test_initials_computed(self, app, seeded_user_id):
        with app.app_context():
            result = get_user_by_id(seeded_user_id)
        assert result["initials"] == "DU"

    def test_member_since_format(self, app, seeded_user_id):
        with app.app_context():
            result = get_user_by_id(seeded_user_id)
        assert re.match(r"^[A-Z][a-z]+ \d{4}$", result["member_since"]), (
            f"Expected 'Month YYYY' format, got: {result['member_since']}"
        )

    def test_unknown_id_returns_none(self, app):
        with app.app_context():
            assert get_user_by_id(99999) is None


# ── get_summary_stats ─────────────────────────────────────────────── #

class TestGetSummaryStats:
    def test_total_spent(self, app, seeded_user_id):
        with app.app_context():
            result = get_summary_stats(seeded_user_id)
        assert result["total_spent"] == "281.49"

    def test_transaction_count(self, app, seeded_user_id):
        with app.app_context():
            result = get_summary_stats(seeded_user_id)
        assert result["transaction_count"] == 8

    def test_top_category(self, app, seeded_user_id):
        with app.app_context():
            result = get_summary_stats(seeded_user_id)
        assert result["top_category"] == "Bills"

    def test_no_expenses_returns_zeros(self, app):
        import database.db as db_module

        conn = db_module.get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty User", "empty@spendly.com", "x"),
        )
        empty_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with app.app_context():
            result = get_summary_stats(empty_id)

        assert result["total_spent"] == "0.00"
        assert result["transaction_count"] == 0
        assert result["top_category"] == "—"


# ── get_recent_transactions ───────────────────────────────────────── #

class TestGetRecentTransactions:
    def test_returns_all_8_by_default(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        assert len(result) == 8

    def test_respects_custom_limit(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id, limit=3)
        assert len(result) == 3

    def test_ordered_newest_first(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        # day 21 Other is newest, day 2 Food is oldest
        assert result[0]["category"] == "Other"
        assert result[-1]["category"] == "Food"

    def test_date_format(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        for tx in result:
            assert re.match(r"^\d{2} [A-Z][a-z]{2} \d{4}$", tx["date"]), (
                f"Bad date format: {tx['date']}"
            )

    def test_amount_has_two_decimal_places(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        for tx in result:
            assert re.match(r"^\d[\d,]*\.\d{2}$", tx["amount"]), (
                f"Bad amount format: {tx['amount']}"
            )

    def test_amount_has_no_rupee_symbol(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        for tx in result:
            assert "₹" not in tx["amount"]

    def test_required_keys_present(self, app, seeded_user_id):
        with app.app_context():
            result = get_recent_transactions(seeded_user_id)
        for tx in result:
            assert {"date", "description", "category", "amount"} <= set(tx.keys())

    def test_no_expenses_returns_empty_list(self, app):
        import database.db as db_module

        conn = db_module.get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty2 User", "empty2@spendly.com", "x"),
        )
        empty_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with app.app_context():
            result = get_recent_transactions(empty_id)
        assert result == []


# ── get_category_breakdown ────────────────────────────────────────── #

class TestGetCategoryBreakdown:
    def test_highest_spend_category_is_first(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        assert result[0]["name"] == "Bills"

    def test_pct_values_sum_to_100(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        assert sum(cat["pct"] for cat in result) == 100

    def test_bar_class_valid(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        for cat in result:
            assert cat["bar_class"] in _VALID_BAR_CLASSES, (
                f"Invalid bar_class: {cat['bar_class']}"
            )

    def test_slug_is_lowercase_name(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        for cat in result:
            assert cat["slug"] == cat["name"].lower()

    def test_top_category_amount(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        assert result[0]["amount"] == "89.99"

    def test_required_keys_present(self, app, seeded_user_id):
        with app.app_context():
            result = get_category_breakdown(seeded_user_id)
        for cat in result:
            assert {"name", "slug", "amount", "pct", "bar_class"} <= set(cat.keys())

    def test_no_expenses_returns_empty_list(self, app):
        import database.db as db_module

        conn = db_module.get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty3 User", "empty3@spendly.com", "x"),
        )
        empty_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with app.app_context():
            result = get_category_breakdown(empty_id)
        assert result == []


# ── /profile route ────────────────────────────────────────────────── #

class TestProfileRoute:
    def _login_as_demo(self, client):
        import database.db as db_module

        conn = db_module.get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        conn.close()
        with client.session_transaction() as sess:
            sess["user_id"] = row["id"]

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_authenticated_returns_200(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert response.status_code == 200

    def test_shows_real_user_name(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"Demo User" in response.data

    def test_shows_real_email(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"demo@spendly.com" in response.data

    def test_shows_correct_total(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"281.49" in response.data

    def test_shows_top_category(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"Bills" in response.data

    def test_shows_rupee_symbol(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert "₹".encode() in response.data
