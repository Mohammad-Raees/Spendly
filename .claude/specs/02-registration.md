# Spec: Registration

## Overview

This step implements account creation for Spendly. `GET /register` already
renders `register.html`, but submitting the form does nothing — there is no
`POST /register` handler and no way to persist a new user. This step adds
the `POST /register` route, the database functions needed to check for
duplicate emails and insert a new user, and wires the existing registration
form up to that logic. It does not implement login sessions, logout, or the
profile page — those remain stubs for later steps.

## Depends on

- Step 1 (Database setup) — `users` table, `get_db()`, and `init_db()` must
  already exist in `database/db.py`. Confirmed: they do.

## Routes

- `POST /register` — create a new user account from form data — public
- `GET /register` — already implemented, unchanged

If validation fails (missing fields, invalid email, password too short, or
email already registered), re-render `register.html` with an `error`
message and HTTP 200 — do not redirect.

On success, redirect to `GET /login` (no session/auto-login yet — that is
introduced when the login step is implemented).

## Database changes

No new tables or columns — the `users` table from Step 1 already has the
required columns (`name`, `email`, `password_hash`).

New functions in `database/db.py`:

- `get_user_by_email(email)` — returns the user row matching `email`, or
  `None`. Used to check for duplicates before insert.
- `create_user(name, email, password_hash)` — inserts a new row into
  `users` using a parameterized query and returns the new `user_id`.

## Templates

- **Create:** none
- **Modify:** `templates/register.html` — change the form's hardcoded
  `action="/register"` to `action="{{ url_for('register') }}"` per the
  "never hardcode URLs" rule. No other markup changes needed; the existing
  `{% if error %}` block already supports displaying validation errors.

## Files to change

- `app.py` — add `POST` handling to the `register` route (form parsing,
  validation, calling `database/db.py` functions, redirect or re-render)
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — fix hardcoded form action

## Files to create

- None

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access happens in `database/db.py`, never inline in `app.py`
- Use `url_for()` for every internal link/redirect — never hardcode URLs

## Definition of done

- [ ] Submitting the register form with valid name/email/password creates a
      row in the `users` table with a hashed password
- [ ] Submitting with an email that already exists shows an error on
      `register.html` and does not create a duplicate row
- [ ] Submitting with a missing field shows an error on `register.html`
      and does not hit the database
- [ ] On successful registration, the browser is redirected to `/login`
- [ ] `register.html`'s form posts via `url_for('register')`, not a
      hardcoded path
- [ ] App starts without errors and `GET /register` still renders correctly
