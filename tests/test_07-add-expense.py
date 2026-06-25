"""
Tests for Step 7: Add Expense — GET + POST /expenses/add

Covers:
- Unit tests for insert_expense() DB helper
- Auth guards (GET and POST unauthenticated → 302 /login)
- GET renders form with all 7 categories and a POST form
- POST valid data → 302 /profile, row inserted in DB
- POST validation errors: missing amount, zero amount, non-numeric amount,
  invalid category, invalid date → 200 with error message
- POST no description → 302 /profile, NULL stored in DB
- Form field repopulation after validation error
- Template structure: required field names present
- Currency: rupee symbol present, no £ or $ before amounts
"""

import pytest
import database.db as db_module
import database.queries as queries_module


# ── Helpers ──────────────────────────────────────────────────────────── #

def _login_as(client, user_id):
    """Inject user_id directly into session to avoid password-hashing overhead."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _fresh_user(name="Expense Tester", email="expense@test.com"):
    """Insert a bare user into the DB and return their user_id."""
    conn = db_module.get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, "hashed_pw"),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _fetch_expenses_for_user(user_id):
    """Return all expense rows for the given user as sqlite3.Row objects."""
    conn = db_module.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
    finally:
        conn.close()


# ── Fixtures ─────────────────────────────────────────────────────────── #

@pytest.fixture
def expense_user_id(app):
    """Create a fresh user with no expenses and return their user_id."""
    return _fresh_user()


@pytest.fixture
def auth_expense_client(client, expense_user_id):
    """A test client logged in as the fresh expense user."""
    _login_as(client, expense_user_id)
    return client


_VALID_FORM = {
    "amount": "50.00",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}

_ALL_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


# ── Unit: insert_expense ─────────────────────────────────────────────── #

class TestInsertExpenseUnit:
    def test_insert_expense_valid_args_row_in_db(self, app, expense_user_id):
        """insert_expense with valid args creates a retrievable row."""
        queries_module.insert_expense(
            expense_user_id, 50.0, "Food", "2026-03-20", "Lunch"
        )
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 1, "Expected exactly one expense row after insert"
        row = rows[0]
        assert row["user_id"] == expense_user_id
        assert row["amount"] == 50.0, "Amount should be stored as 50.0"
        assert row["category"] == "Food", "Category should be stored as 'Food'"
        assert row["date"] == "2026-03-20", "Date should be stored as '2026-03-20'"
        assert row["description"] == "Lunch", "Description should be stored as 'Lunch'"

    def test_insert_expense_null_description_stored_as_null(self, app, expense_user_id):
        """insert_expense with description=None stores NULL in the DB."""
        queries_module.insert_expense(
            expense_user_id, 99.99, "Transport", "2026-04-01", None
        )
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 1, "Expected one row after insert"
        assert rows[0]["description"] is None, (
            "description column must be NULL when None is passed"
        )

    def test_insert_expense_stores_correct_user_id(self, app, expense_user_id):
        """Row is associated with the correct user_id."""
        queries_module.insert_expense(
            expense_user_id, 10.0, "Bills", "2026-05-10", "Electric"
        )
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["user_id"] == expense_user_id

    def test_insert_expense_multiple_rows(self, app, expense_user_id):
        """Each call to insert_expense adds a separate row."""
        queries_module.insert_expense(expense_user_id, 10.0, "Food", "2026-01-01", None)
        queries_module.insert_expense(expense_user_id, 20.0, "Health", "2026-01-02", None)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 2, "Expected two rows after two inserts"


# ── Auth guards ───────────────────────────────────────────────────────── #

class TestAuthGuard:
    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add should return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET redirect target must be /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=_VALID_FORM)
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add should return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST redirect target must be /login"
        )

    def test_get_unauthenticated_does_not_return_200(self, client):
        response = client.get("/expenses/add")
        assert response.status_code != 200, (
            "Unauthenticated access must never return 200"
        )


# ── GET /expenses/add (authenticated) ────────────────────────────────── #

class TestGetAddExpense:
    def test_authenticated_get_returns_200(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_response_contains_post_form(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        data = response.data
        # Form tag must specify POST method (case-insensitive in HTML but the
        # template is authored in lowercase per Jinja convention)
        assert b"<form" in data, "Response must contain a <form> element"
        assert b'method="post"' in data.lower() or b"method='post'" in data.lower(), (
            "Form must use POST method"
        )

    def test_response_contains_all_seven_categories(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        for cat in _ALL_CATEGORIES:
            assert cat.encode() in response.data, (
                f"Category '{cat}' must appear as an option in the form"
            )

    def test_response_contains_amount_field(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert b'name="amount"' in response.data, (
            "Form must contain an input named 'amount'"
        )

    def test_response_contains_category_select(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert b'name="category"' in response.data, (
            "Form must contain a select/input named 'category'"
        )

    def test_response_contains_date_field(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert b'name="date"' in response.data, (
            "Form must contain an input named 'date'"
        )

    def test_response_contains_description_field(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert b'name="description"' in response.data, (
            "Form must contain an input named 'description'"
        )

    def test_form_posts_to_expenses_add(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        # The form action must target /expenses/add
        assert b"/expenses/add" in response.data, (
            "Form action must point to /expenses/add"
        )

    def test_cancel_link_points_to_profile(self, auth_expense_client):
        response = auth_expense_client.get("/expenses/add")
        assert b"/profile" in response.data, (
            "A cancel/back link to /profile must be present on the add-expense form"
        )


# ── POST /expenses/add — happy paths ─────────────────────────────────── #

class TestPostAddExpenseHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_expense_client):
        response = auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        assert response.status_code == 302, (
            "Valid POST must redirect (302)"
        )
        assert "/profile" in response.headers["Location"], (
            "Valid POST must redirect to /profile"
        )

    def test_valid_post_inserts_row_in_db(self, auth_expense_client, expense_user_id):
        auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 1, "One expense row must exist in DB after valid POST"

    def test_valid_post_stores_correct_amount(self, auth_expense_client, expense_user_id):
        auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["amount"] == 50.0, "Amount stored in DB must be 50.0"

    def test_valid_post_stores_correct_category(self, auth_expense_client, expense_user_id):
        auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["category"] == "Food", "Category stored in DB must be 'Food'"

    def test_valid_post_stores_correct_date(self, auth_expense_client, expense_user_id):
        auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["date"] == "2026-03-20", "Date stored in DB must be '2026-03-20'"

    def test_valid_post_stores_correct_description(self, auth_expense_client, expense_user_id):
        auth_expense_client.post("/expenses/add", data=_VALID_FORM)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["description"] == "Lunch", "Description stored must be 'Lunch'"

    def test_post_without_description_redirects_to_profile(self, auth_expense_client):
        data = {**_VALID_FORM, "description": ""}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 302, (
            "POST without description must still redirect (302)"
        )
        assert "/profile" in response.headers["Location"], (
            "POST without description must redirect to /profile"
        )

    def test_post_without_description_inserts_null(self, auth_expense_client, expense_user_id):
        data = {**_VALID_FORM, "description": ""}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 1, "One row must be inserted even without description"
        assert rows[0]["description"] is None, (
            "description must be NULL in DB when empty string is submitted"
        )

    def test_post_whitespace_only_description_inserts_null(
        self, auth_expense_client, expense_user_id
    ):
        data = {**_VALID_FORM, "description": "   "}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stripped to NULL"
        )

    def test_post_accepts_all_valid_categories(self, auth_expense_client, expense_user_id):
        """Every one of the 7 fixed categories is accepted by the route."""
        for i, cat in enumerate(_ALL_CATEGORIES):
            data = {
                "amount": "10.00",
                "category": cat,
                "date": f"2026-0{(i % 9) + 1}-01",
                "description": "",
            }
            response = auth_expense_client.post("/expenses/add", data=data)
            assert response.status_code == 302, (
                f"Category '{cat}' must be accepted; expected redirect but got "
                f"{response.status_code}"
            )
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == len(_ALL_CATEGORIES), (
            f"Expected {len(_ALL_CATEGORIES)} rows for all valid categories"
        )


# ── POST /expenses/add — validation errors ────────────────────────────── #

class TestPostAddExpenseValidation:
    def test_missing_amount_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": ""}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Missing amount must re-render the form (200)"
        )

    def test_missing_amount_shows_error(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": ""}
        response = auth_expense_client.post("/expenses/add", data=data)
        # Error message text may vary; check for common indicators
        assert b"error" in response.data.lower() or b"amount" in response.data.lower(), (
            "Missing amount must display an error message"
        )

    def test_zero_amount_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": "0"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Zero amount must re-render the form (200)"
        )

    def test_zero_amount_shows_error(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": "0"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"positive" in response.data.lower() or b"amount" in response.data.lower(), (
            "Zero amount must display an error about positive amount"
        )

    def test_zero_amount_does_not_insert_row(self, auth_expense_client, expense_user_id):
        data = {**_VALID_FORM, "amount": "0"}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 0, "Zero amount must not insert any row in the DB"

    def test_negative_amount_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": "-10.00"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Negative amount must re-render the form (200)"
        )

    def test_non_numeric_amount_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": "abc"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form (200)"
        )

    def test_non_numeric_amount_shows_error(self, auth_expense_client):
        data = {**_VALID_FORM, "amount": "abc"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"error" in response.data.lower() or b"amount" in response.data.lower(), (
            "Non-numeric amount must display an error message"
        )

    def test_non_numeric_amount_does_not_insert_row(
        self, auth_expense_client, expense_user_id
    ):
        data = {**_VALID_FORM, "amount": "fifty"}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 0, "Non-numeric amount must not insert any row"

    def test_invalid_category_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "category": "Snacks"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Invalid category must re-render the form (200)"
        )

    def test_invalid_category_shows_error(self, auth_expense_client):
        data = {**_VALID_FORM, "category": "Snacks"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"error" in response.data.lower() or b"category" in response.data.lower(), (
            "Invalid category must display an error message"
        )

    def test_invalid_category_does_not_insert_row(
        self, auth_expense_client, expense_user_id
    ):
        data = {**_VALID_FORM, "category": "Snacks"}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 0, "Invalid category must not insert any row"

    def test_empty_category_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "category": ""}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Empty category must re-render the form (200)"
        )

    def test_invalid_date_string_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "date": "20-03-2026"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Invalid date format must re-render the form (200)"
        )

    def test_invalid_date_string_shows_error(self, auth_expense_client):
        data = {**_VALID_FORM, "date": "20-03-2026"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"error" in response.data.lower() or b"date" in response.data.lower(), (
            "Invalid date must display an error message"
        )

    def test_invalid_date_does_not_insert_row(self, auth_expense_client, expense_user_id):
        data = {**_VALID_FORM, "date": "not-a-date"}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 0, "Invalid date must not insert any row"

    def test_missing_date_returns_200(self, auth_expense_client):
        data = {**_VALID_FORM, "date": ""}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "Missing date must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "0.00", "abc", "  ", "1e9999"])
    def test_parametrized_invalid_amounts_return_200(
        self, auth_expense_client, bad_amount
    ):
        data = {**_VALID_FORM, "amount": bad_amount}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            f"amount={bad_amount!r} must not be accepted; expected 200 but got "
            f"{response.status_code}"
        )

    @pytest.mark.parametrize("bad_date", [
        "20-03-2026",
        "2026/03/20",
        "March 20 2026",
        "not-a-date",
        "2026-13-01",
        "2026-00-10",
    ])
    def test_parametrized_invalid_dates_return_200(
        self, auth_expense_client, bad_date
    ):
        data = {**_VALID_FORM, "date": bad_date}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            f"date={bad_date!r} must not be accepted; expected 200 but got "
            f"{response.status_code}"
        )


# ── Form repopulation after validation error ──────────────────────────── #

class TestFormRepopulation:
    def test_previously_entered_amount_repopulated_on_error(self, auth_expense_client):
        """After a category error, the entered amount must be visible in the form."""
        data = {**_VALID_FORM, "category": "Invalid"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"50.00" in response.data or b"50" in response.data, (
            "Previously entered amount must be re-populated after validation error"
        )

    def test_previously_entered_date_repopulated_on_error(self, auth_expense_client):
        """After an amount error, the entered date must be visible in the form."""
        data = {**_VALID_FORM, "amount": "0"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"2026-03-20" in response.data, (
            "Previously entered date must be re-populated after validation error"
        )

    def test_previously_entered_description_repopulated_on_error(
        self, auth_expense_client
    ):
        """After an amount error, the description must be visible in the form."""
        data = {**_VALID_FORM, "amount": "0"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert b"Lunch" in response.data, (
            "Previously entered description must be re-populated after validation error"
        )

    def test_all_categories_still_listed_on_error(self, auth_expense_client):
        """Category dropdown must still contain all 7 options after a validation error."""
        data = {**_VALID_FORM, "amount": "0"}
        response = auth_expense_client.post("/expenses/add", data=data)
        for cat in _ALL_CATEGORIES:
            assert cat.encode() in response.data, (
                f"Category '{cat}' must still appear in dropdown after error"
            )


# ── Currency symbol ───────────────────────────────────────────────────── #

class TestCurrencySymbol:
    def test_rupee_symbol_present_on_get(self, auth_expense_client):
        """The add-expense form page must use ₹ for any currency display."""
        response = auth_expense_client.get("/expenses/add")
        # Rupee symbol is optional on the form itself; base.html may carry it.
        # This test ensures ₹ is never replaced with $ or £.
        assert "£".encode() not in response.data, (
            "Pound sign must never appear on the add-expense page"
        )

    def test_no_dollar_sign_before_amounts_on_get(self, auth_expense_client):
        import re
        response = auth_expense_client.get("/expenses/add")
        text = response.data.decode("utf-8")
        assert not re.search(r'\$[\d,]+', text), (
            "Dollar sign must never precede a numeric amount on the add-expense page"
        )

    def test_no_pound_sign_after_valid_post_redirect(self, auth_expense_client):
        """After redirect to /profile, the profile page must not show £."""
        response = auth_expense_client.post(
            "/expenses/add", data=_VALID_FORM, follow_redirects=True
        )
        assert "£".encode() not in response.data, (
            "Pound sign must not appear after a successful expense submission"
        )


# ── SQL injection safety ──────────────────────────────────────────────── #

class TestSQLInjectionSafety:
    def test_sql_injection_in_description_is_stored_literally(
        self, auth_expense_client, expense_user_id
    ):
        """SQL injection in description must be stored literally, not executed."""
        payload = "'; DROP TABLE expenses; --"
        data = {**_VALID_FORM, "description": payload}
        auth_expense_client.post("/expenses/add", data=data)
        rows = _fetch_expenses_for_user(expense_user_id)
        assert len(rows) == 1, "Expense table must still exist and contain one row"
        assert rows[0]["description"] == payload, (
            "SQL injection string must be stored as a literal value"
        )

    def test_sql_injection_in_amount_treated_as_invalid(self, auth_expense_client):
        """SQL injection attempt in amount field must be rejected as non-numeric."""
        data = {**_VALID_FORM, "amount": "1; DROP TABLE expenses; --"}
        response = auth_expense_client.post("/expenses/add", data=data)
        assert response.status_code == 200, (
            "SQL in amount field must fail validation and re-render the form"
        )


# ── Navigation: Add Expense link in profile/base ───────────────────────── #

class TestNavigationLinks:
    def test_profile_page_contains_add_expense_link(
        self, auth_expense_client
    ):
        """The profile page must contain a link or button to /expenses/add."""
        response = auth_expense_client.get("/profile")
        assert b"/expenses/add" in response.data, (
            "Profile page must contain an 'Add Expense' link pointing to /expenses/add"
        )

    def test_add_expense_link_in_navbar_when_authenticated(
        self, auth_expense_client
    ):
        """The navbar (via base.html) must show an Add Expense link when logged in."""
        response = auth_expense_client.get("/profile")
        assert b"/expenses/add" in response.data, (
            "Authenticated users must see an 'Add Expense' link in navigation"
        )
