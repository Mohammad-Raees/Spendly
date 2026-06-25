"""
Tests for Step 6: Date Filter on the /profile page.

Seeded data (demo@spendly.com / demo123) — 8 expenses in the current month.
Each test that needs date-bounded assertions inserts its own deterministic
expenses using fixed dates so assertions are month-independent.

Fixed-date seed used in date-filter tests:
  2024-01-05  Food         100.00  January food
  2024-01-20  Transport     50.00  January transport
  2024-03-10  Bills        200.00  March bills
  2024-06-15  Health        75.00  June health

Total all-time: 425.00  |  Top category: Bills (200.00)
Jan-only (05–20): 150.00, 2 transactions, categories: Food + Transport
Mar-only:         200.00, 1 transaction, category:  Bills
After 2024-02-01: 275.00 (March + June)
Before 2024-02-28: 150.00 (Jan only)
"""

import pytest
import database.db as db_module


# ── Helpers ─────────────────────────────────────────────────────────── #

def _login_as(client, user_id):
    """Inject user_id directly into session to avoid password-hashing overhead."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _create_user_with_expenses(fixed_expenses):
    """
    Insert a fresh user and the given list of (amount, category, date, description)
    tuples into the test DB. Returns the new user_id.
    """
    conn = db_module.get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Filter User", "filter@spendly.com", "hashed"),
        )
        user_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [(user_id, amt, cat, dt, desc) for amt, cat, dt, desc in fixed_expenses],
        )
        conn.commit()
        return user_id
    finally:
        conn.close()


_FIXED_EXPENSES = [
    (100.00, "Food",      "2024-01-05", "January food"),
    (50.00,  "Transport", "2024-01-20", "January transport"),
    (200.00, "Bills",     "2024-03-10", "March bills"),
    (75.00,  "Health",    "2024-06-15", "June health"),
]


@pytest.fixture
def filter_user_id(app):
    """Create a fresh user with fixed-date expenses and return their user_id."""
    return _create_user_with_expenses(_FIXED_EXPENSES)


@pytest.fixture
def filter_client(client, filter_user_id):
    """A logged-in test client for the filter user."""
    _login_as(client, filter_user_id)
    return client


# ── Auth guard ───────────────────────────────────────────────────────── #

class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated user"
        assert "/login" in response.headers["Location"], (
            "Redirect target should be /login"
        )

    def test_unauthenticated_with_date_params_redirects_to_login(self, client):
        response = client.get("/profile?date_from=2024-01-01&date_to=2024-12-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ── No-filter (all-time) view ─────────────────────────────────────────── #

class TestNoFilterView:
    def test_returns_200(self, filter_client):
        response = filter_client.get("/profile")
        assert response.status_code == 200, "Profile page should return 200"

    def test_shows_all_expenses_total(self, filter_client):
        response = filter_client.get("/profile")
        assert b"425.00" in response.data, (
            "All-time total (425.00) should appear with no filter active"
        )

    def test_shows_all_transaction_count(self, filter_client):
        response = filter_client.get("/profile")
        # transaction_count stat rendered in the stats section
        assert b"4" in response.data, (
            "All 4 transactions should be counted when no filter is active"
        )

    def test_shows_rupee_symbol(self, filter_client):
        response = filter_client.get("/profile")
        assert "₹".encode() in response.data, "Rupee symbol must appear in unfiltered view"

    def test_no_filter_banner_when_no_params(self, filter_client):
        response = filter_client.get("/profile")
        assert b"date-filter-banner" not in response.data, (
            "Filter banner must NOT appear when no date params are supplied"
        )

    def test_shows_top_category(self, filter_client):
        response = filter_client.get("/profile")
        assert b"Bills" in response.data, (
            "Top category (Bills, 200.00) should appear in all-time view"
        )


# ── Both-dates filter ────────────────────────────────────────────────── #

class TestBothDatesFilter:
    def test_returns_200(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert response.status_code == 200

    def test_filters_total_to_january(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # January: 100.00 + 50.00 = 150.00
        assert b"150.00" in response.data, (
            "Total should be 150.00 for January 2024 filter"
        )

    def test_excludes_out_of_range_expenses(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # March 200.00 and June 75.00 must NOT appear as transaction amounts
        assert b"200.00" not in response.data, (
            "March expense (200.00) must be excluded from Jan filter"
        )
        assert b"75.00" not in response.data, (
            "June expense (75.00) must be excluded from Jan filter"
        )

    def test_transaction_count_filtered(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # Only 2 transactions in January
        assert b"2" in response.data

    def test_category_breakdown_filtered(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # Food and Transport appear; Bills and Health must not appear as categories
        assert b"Food" in response.data
        assert b"Transport" in response.data

    def test_out_of_range_categories_absent(self, filter_client):
        # Bills only exist in March — should not appear in Jan-only filter
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # Bills appears in stats section (top category) only if it is in range;
        # for Jan-only filter Food is the larger category.
        # Check the category breakdown section does not list Bills
        # We check that 200.00 is not present (Bills amount), which is distinct enough
        assert b"200.00" not in response.data


# ── Only date_from filter ────────────────────────────────────────────── #

class TestDateFromOnlyFilter:
    def test_filters_to_expenses_on_or_after_date(self, filter_client):
        # From 2024-02-01: March (200) + June (75) = 275
        response = filter_client.get("/profile?date_from=2024-02-01")
        assert response.status_code == 200
        assert b"275.00" in response.data, (
            "Total should be 275.00 (March + June) when date_from=2024-02-01"
        )

    def test_excludes_expenses_before_date_from(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-02-01")
        # January expenses (100.00, 50.00) must not appear as totals or transactions
        assert b"January food" not in response.data
        assert b"January transport" not in response.data

    def test_includes_expenses_on_date_from_itself(self, filter_client):
        # date_from=2024-01-05 should include the expense on exactly that date
        response = filter_client.get("/profile?date_from=2024-01-05")
        assert b"January food" in response.data, (
            "Expense on date_from itself should be included (inclusive lower bound)"
        )

    def test_filter_banner_appears_with_date_from_only(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-02-01")
        assert b"date-filter-banner" in response.data, (
            "Filter banner must appear when date_from is supplied"
        )

    def test_returns_200_with_date_from_only(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-02-01")
        assert response.status_code == 200


# ── Only date_to filter ───────────────────────────────────────────────── #

class TestDateToOnlyFilter:
    def test_filters_to_expenses_on_or_before_date(self, filter_client):
        # Up to 2024-01-31: Food (100) + Transport (50) = 150
        response = filter_client.get("/profile?date_to=2024-01-31")
        assert response.status_code == 200
        assert b"150.00" in response.data, (
            "Total should be 150.00 for date_to=2024-01-31"
        )

    def test_excludes_expenses_after_date_to(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-01-31")
        assert b"March bills" not in response.data
        assert b"June health" not in response.data

    def test_includes_expenses_on_date_to_itself(self, filter_client):
        # date_to=2024-01-20 should include the expense on exactly that date
        response = filter_client.get("/profile?date_to=2024-01-20")
        assert b"January transport" in response.data, (
            "Expense on date_to itself should be included (inclusive upper bound)"
        )

    def test_filter_banner_appears_with_date_to_only(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-01-31")
        assert b"date-filter-banner" in response.data, (
            "Filter banner must appear when date_to is supplied"
        )

    def test_returns_200_with_date_to_only(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-01-31")
        assert response.status_code == 200


# ── Filter banner ────────────────────────────────────────────────────── #

class TestFilterBanner:
    def test_banner_present_with_both_dates(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert b"date-filter-banner" in response.data, (
            "Banner must appear when both date_from and date_to are provided"
        )

    def test_banner_shows_from_date_display(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-05&date_to=2024-01-31")
        # date_from_display rendered as "05 Jan 2024"
        assert b"05 Jan 2024" in response.data, (
            "Banner should display date_from in human-readable format"
        )

    def test_banner_shows_to_date_display(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-05&date_to=2024-01-31")
        assert b"31 Jan 2024" in response.data, (
            "Banner should display date_to in human-readable format"
        )

    def test_banner_absent_when_no_filter(self, filter_client):
        response = filter_client.get("/profile")
        assert b"date-filter-banner" not in response.data

    def test_banner_present_with_date_from_only(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-03-01")
        assert b"date-filter-banner" in response.data

    def test_banner_present_with_date_to_only(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-03-31")
        assert b"date-filter-banner" in response.data


# ── Pre-filled inputs ────────────────────────────────────────────────── #

class TestPrefilledInputs:
    def test_date_from_input_prefilled(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert b'value="2024-01-01"' in response.data, (
            "date_from input must be pre-filled with the submitted value"
        )

    def test_date_to_input_prefilled(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert b'value="2024-01-31"' in response.data, (
            "date_to input must be pre-filled with the submitted value"
        )

    def test_inputs_empty_when_no_filter(self, filter_client):
        response = filter_client.get("/profile")
        # Both inputs should have value="" when no filter is active
        assert b'value=""' in response.data, (
            "Date inputs must be empty when no filter params are provided"
        )

    def test_date_from_prefilled_when_only_date_from_given(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-06-01")
        assert b'value="2024-06-01"' in response.data

    def test_date_to_prefilled_when_only_date_to_given(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-06-30")
        assert b'value="2024-06-30"' in response.data


# ── Clear link ───────────────────────────────────────────────────────── #

class TestClearLink:
    def test_clear_link_present_in_filter_form(self, filter_client):
        response = filter_client.get("/profile")
        assert b"Clear" in response.data, "Clear link must be present on the profile page"

    def test_clear_link_points_to_profile_without_params(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # The clear link's href must be /profile (no query params)
        assert b'href="/profile"' in response.data, (
            "Clear link must point to /profile with no query parameters"
        )

    def test_visiting_profile_without_params_returns_all_expenses(self, filter_client):
        # Simulate what clicking Clear does: GET /profile with no params
        response = filter_client.get("/profile")
        assert b"425.00" in response.data, (
            "Visiting /profile with no params should show all-time total"
        )


# ── Malformed date handling ───────────────────────────────────────────── #

class TestMalformedDates:
    def test_malformed_date_from_renders_200(self, filter_client):
        response = filter_client.get("/profile?date_from=not-a-date")
        assert response.status_code == 200, (
            "Malformed date_from must not crash the page"
        )

    def test_malformed_date_from_shows_all_expenses(self, filter_client):
        response = filter_client.get("/profile?date_from=not-a-date")
        assert b"425.00" in response.data, (
            "Malformed date_from must be ignored; unfiltered total should appear"
        )

    def test_malformed_date_to_renders_200(self, filter_client):
        response = filter_client.get("/profile?date_to=13/99/2024")
        assert response.status_code == 200

    def test_malformed_date_to_shows_all_expenses(self, filter_client):
        response = filter_client.get("/profile?date_to=13/99/2024")
        assert b"425.00" in response.data, (
            "Malformed date_to must be ignored; unfiltered total should appear"
        )

    def test_both_dates_malformed_shows_all_expenses(self, filter_client):
        response = filter_client.get("/profile?date_from=foo&date_to=bar")
        assert response.status_code == 200
        assert b"425.00" in response.data, (
            "Both malformed dates must be ignored; unfiltered total should appear"
        )

    def test_malformed_date_no_filter_banner(self, filter_client):
        response = filter_client.get("/profile?date_from=not-a-date")
        assert b"date-filter-banner" not in response.data, (
            "Filter banner must NOT appear when the date value is malformed (treated as absent)"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2024/01/01",
        "01-01-2024",
        "2024-13-01",
        "2024-00-10",
        "",
    ])
    def test_various_malformed_date_from_values_do_not_crash(self, filter_client, bad_date):
        response = filter_client.get(f"/profile?date_from={bad_date}")
        assert response.status_code == 200, (
            f"date_from={bad_date!r} must not crash the page"
        )


# ── Empty date range ──────────────────────────────────────────────────── #

class TestEmptyDateRange:
    def test_returns_200_when_no_expenses_in_range(self, filter_client):
        # 2099-01-01 to 2099-12-31 — no expenses exist that far in the future
        response = filter_client.get("/profile?date_from=2099-01-01&date_to=2099-12-31")
        assert response.status_code == 200, (
            "Empty date range must not raise an exception"
        )

    def test_shows_zero_total_for_empty_range(self, filter_client):
        response = filter_client.get("/profile?date_from=2099-01-01&date_to=2099-12-31")
        assert b"0.00" in response.data, (
            "Empty range should display ₹0.00 total"
        )

    def test_shows_zero_transaction_count_for_empty_range(self, filter_client):
        response = filter_client.get("/profile?date_from=2099-01-01&date_to=2099-12-31")
        assert b"0" in response.data, (
            "Empty range should show 0 transactions"
        )

    def test_no_category_rows_for_empty_range(self, filter_client):
        response = filter_client.get("/profile?date_from=2099-01-01&date_to=2099-12-31")
        # When categories list is empty, none of our seeded categories should appear
        # in the breakdown section. The simplest check: no category-badge divs for
        # known categories tied to amounts.
        assert b"January food" not in response.data
        assert b"March bills" not in response.data

    def test_rupee_symbol_still_present_in_empty_range(self, filter_client):
        response = filter_client.get("/profile?date_from=2099-01-01&date_to=2099-12-31")
        assert "₹".encode() in response.data, (
            "Rupee symbol must still appear even when no expenses match the filter"
        )


# ── Inverted date swap ────────────────────────────────────────────────── #

class TestInvertedDateSwap:
    def test_swapped_dates_still_return_200(self, filter_client):
        # date_from is after date_to — should be silently swapped
        response = filter_client.get("/profile?date_from=2024-01-31&date_to=2024-01-01")
        assert response.status_code == 200, (
            "Inverted date range must not cause an error"
        )

    def test_swapped_dates_return_correct_results(self, filter_client):
        # Providing dates inverted: from=2024-01-31 to=2024-01-01
        # After swap: effective range is 2024-01-01 to 2024-01-31 → total 150.00
        response = filter_client.get("/profile?date_from=2024-01-31&date_to=2024-01-01")
        assert b"150.00" in response.data, (
            "Inverted dates should be swapped silently; January total (150.00) expected"
        )

    def test_swapped_dates_exclude_out_of_range(self, filter_client):
        # Even with inverted params, March and June expenses should stay out of range
        response = filter_client.get("/profile?date_from=2024-01-31&date_to=2024-01-01")
        assert b"March bills" not in response.data

    def test_swapped_dates_show_filter_banner(self, filter_client):
        # Both params are present (even if inverted) → banner must show
        response = filter_client.get("/profile?date_from=2024-01-31&date_to=2024-01-01")
        assert b"date-filter-banner" in response.data, (
            "Filter banner must appear even when dates were supplied in inverted order"
        )


# ── Rupee symbol in filtered views ───────────────────────────────────── #

class TestRupeeSymbolInFilteredView:
    def test_rupee_symbol_in_filtered_view(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert "₹".encode() in response.data, (
            "Rupee symbol must appear in a filtered view"
        )

    def test_rupee_symbol_in_date_from_only_view(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-02-01")
        assert "₹".encode() in response.data

    def test_rupee_symbol_in_date_to_only_view(self, filter_client):
        response = filter_client.get("/profile?date_to=2024-01-31")
        assert "₹".encode() in response.data

    def test_no_dollar_sign_in_filtered_view(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        # Scope to currency amounts only — JS template literals legitimately contain $
        import re
        text = response.data.decode("utf-8")
        assert not re.search(r'\$[\d,]+', text), "Dollar sign must never precede an amount in Spendly"

    def test_no_pound_sign_in_filtered_view(self, filter_client):
        response = filter_client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert "£".encode() not in response.data, "Pound sign must never appear in Spendly"


# ── Filter form structure ────────────────────────────────────────────── #

class TestFilterFormStructure:
    def test_filter_form_present(self, filter_client):
        response = filter_client.get("/profile")
        assert b"date-filter-form" in response.data or b'method="get"' in response.data, (
            "A GET filter form must be present on the profile page"
        )

    def test_date_from_input_present(self, filter_client):
        response = filter_client.get("/profile")
        assert b'name="date_from"' in response.data, (
            "date_from input must be present in the filter form"
        )

    def test_date_to_input_present(self, filter_client):
        response = filter_client.get("/profile")
        assert b'name="date_to"' in response.data, (
            "date_to input must be present in the filter form"
        )

    def test_apply_button_present(self, filter_client):
        response = filter_client.get("/profile")
        assert b"Apply" in response.data, (
            "Submit button labelled 'Apply' must be present"
        )

    def test_clear_button_present(self, filter_client):
        response = filter_client.get("/profile")
        assert b"Clear" in response.data, (
            "'Clear' link must be present in the filter form"
        )

    def test_label_for_date_from(self, filter_client):
        response = filter_client.get("/profile")
        assert b'for="date_from"' in response.data, (
            "Label for date_from input must use for/id association (accessibility)"
        )

    def test_label_for_date_to(self, filter_client):
        response = filter_client.get("/profile")
        assert b'for="date_to"' in response.data, (
            "Label for date_to input must use for/id association (accessibility)"
        )
