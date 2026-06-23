# Spec: Login and Logout

## Overview

Spendly already has working session-based login: `POST /login` in `app.py`
validates credentials and sets `session["user_id"]` on success (this is
ahead of the route table in `CLAUDE.md`, which still lists `/login` as a
GET-only stub — that table is stale, not the source of truth). What is
still missing is the other half of the session lifecycle: `GET /logout`
is a placeholder that returns a raw string instead of clearing the
session, the navbar never reflects whether a visitor is signed in, and an
already-authenticated user can still browse to `/login` and resubmit
credentials. This step closes those gaps so authentication state is fully
usable end-to-end, without touching `/profile` or the `/expenses/*`
stubs, which remain for later steps.

## Depends on

- Step 1 (Database setup) — `users` table, `get_db()`, `get_user_by_email()`.
- Step 2 (Registration) — `create_user()`, working `/register` flow that
  feeds accounts into the login system.
- Existing `POST /login` logic in `app.py` (already implemented, not part
  of this step's scope) — sets `session["user_id"]`.

## Routes

- `GET /logout` — clear the session and redirect to `GET /login` — logged-in
  (if no active session, redirecting straight to `/login` is fine; no error
  needed)
- `GET /login` — modify existing handler: if `session.get("user_id")` is
  already set, redirect to `GET /landing` instead of rendering the form — public
- `GET /register` — modify existing handler: same already-logged-in redirect
  to `GET /landing` as `/login` — public

## Database changes

No database changes.

## Templates

- **Create:** none
- **Modify:** `templates/base.html` — the `nav-links` block currently
  always shows "Sign in" / "Get started". Wrap it in
  `{% if session.user_id %}` / `{% else %}` so logged-in visitors see a
  "Sign out" link (`url_for('logout')`) instead, and signed-out visitors
  keep seeing the current links. `session` is available in Jinja by
  default in Flask, no extra context processor needed.

## Files to change

- `app.py`:
  - Replace the `/logout` placeholder with real logic: clear the session
    (`session.clear()` or `session.pop("user_id", None)`) and redirect to
    `url_for('login')`
  - Add an already-authenticated guard at the top of `login()` and
    `register()` GET/POST handling: if `session.get("user_id")`, redirect
    to `url_for('landing')`
- `templates/base.html` — conditional nav links based on `session.user_id`

## Files to create

- None

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link/redirect — never hardcode URLs
- Do not touch `/profile` or `/expenses/*` stub routes — out of scope for
  this step

## Definition of done

- [ ] Visiting `/logout` while logged in clears the session and redirects
      to `/login`
- [ ] After logout, visiting a page that reads `session["user_id"]` no
      longer treats the visitor as authenticated
- [ ] Visiting `/login` or `/register` while already logged in redirects
      to `/` instead of showing the form
- [ ] Navbar shows "Sign in" / "Get started" when logged out, and "Sign
      out" when logged in
- [ ] Logging in, then clicking "Sign out", returns the visitor to a
      logged-out navbar state
- [ ] App starts without errors and existing `/register` and `/login`
      flows still work as before
