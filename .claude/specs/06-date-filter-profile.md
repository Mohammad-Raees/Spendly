# Spec: Date Filter for Profile Page

## Overview

Step 6 adds a date range filter to the profile page so users can narrow their
transaction history, summary stats, and category breakdown to a specific period.
The filter is submitted as a GET form — query-string parameters `date_from` and
`date_to` — so the filtered view is bookmarkable and survives a page refresh.
When no dates are supplied the page behaves exactly as it does today (all-time).
This step touches only the existing `/profile` route, the three query helpers in
`database/queries.py`, and the `profile.html` template; no new routes or tables
are needed.

## Depends on

- Step 1: Database setup (`expenses` table with a `date TEXT` column exists)
- Step 2: Registration (users exist in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI (template already renders all four sections)
- Step 5: Backend connection (query helpers in `database/queries.py` exist)

## Routes

No new routes. The existing `GET /profile` route is modified to accept optional
query-string parameters:

- `date_from` — ISO date string `YYYY-MM-DD`, inclusive lower bound (optional)
- `date_to`   — ISO date string `YYYY-MM-DD`, inclusive upper bound (optional)

## Database changes

No database changes. The `expenses.date` column (`TEXT`, stored as `YYYY-MM-DD`)
is already suitable for range comparisons using SQL `BETWEEN`.

## Templates

- **Modify**: `templates/profile.html`
  - Add a date-range filter form above the transaction history section.
  - The form uses `method="get"` and `action="{{ url_for('profile') }}"`.
  - Two `<input type="date">` fields: `name="date_from"` and `name="date_to"`.
  - A submit button labelled "Apply".
  - A "Clear" link that points to `url_for('profile')` (no query params).
  - When a filter is active, display a visible "Showing results for …" banner
    so the user knows a filter is in effect.
  - Pre-fill the date inputs with the currently active filter values so the
    user can see and adjust them without retyping.

## Files to change

- `app.py`
  - Read `date_from` and `date_to` from `request.args` in the `profile()` view.
  - Validate that each value, when present, matches `YYYY-MM-DD`; if malformed,
    treat as absent (do not `abort()` — just ignore the bad value).
  - Pass validated `date_from` and `date_to` to all three query helpers.
  - Pass `date_from` and `date_to` back to the template for pre-filling inputs.

- `database/queries.py`
  - `get_summary_stats(user_id, date_from=None, date_to=None)` — add optional
    date-range parameters; extend the `WHERE` clause with `AND date BETWEEN ? AND ?`
    when both are provided, `AND date >= ?` when only `date_from` is provided, and
    `AND date <= ?` when only `date_to` is provided.
  - `get_recent_transactions(user_id, limit=10, date_from=None, date_to=None)` —
    same conditional `WHERE` extension.
  - `get_category_breakdown(user_id, date_from=None, date_to=None)` — same
    conditional `WHERE` extension.
  - All existing callers that omit the new parameters must continue to work
    unchanged (default `None` values guarantee this).

## Files to create

- `static/css/date-filter.css` — styles for the filter form and the active-filter
  banner. Must use CSS variables only — no hardcoded hex values.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL; build the
  `WHERE` clause dynamically by appending to a params list
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags — page-specific styles go in `date-filter.css`
- Currency must always display as ₹ — never £ or $
- Do not raise an error for a missing or malformed date — silently fall back to
  the unfiltered view
- `date_from` must not be after `date_to`; if it is, swap them silently before
  querying (defensive, not an error)
- The filter form must be accessible: `<label>` elements must be associated with
  their `<input>` via `for`/`id`
- Do not change the `limit` default on `get_recent_transactions`

## Definition of done

- [ ] Visiting `/profile` with no query params shows all expenses (unchanged behaviour)
- [ ] Submitting the date filter form with a valid `date_from` and `date_to` filters
      the transaction list, summary stats, and category breakdown to that range
- [ ] The date inputs are pre-filled with the active filter values after the form is submitted
- [ ] A visible banner appears when a filter is active (e.g. "Showing 01 Jan 2026 – 30 Jun 2026")
- [ ] Clicking "Clear" removes the filter and returns to the all-time view
- [ ] Supplying only `date_from` filters to expenses on or after that date
- [ ] Supplying only `date_to` filters to expenses on or before that date
- [ ] A malformed date in the query string (e.g. `date_from=not-a-date`) is silently
      ignored and the page renders the unfiltered view without an error
- [ ] All amounts in the filtered view still display the ₹ symbol
- [ ] An empty date range (no expenses match) shows ₹0.00 total, 0 transactions,
      and no category rows — no exceptions
