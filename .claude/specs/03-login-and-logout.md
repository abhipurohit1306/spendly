# Spec: Login and Logout

## Overview
This feature lets existing Spendly users sign in and sign out. The `/login`
page and template already exist but only render a static form, and
`/logout` is still a raw-string stub. This step wires the login form up to
`POST /login`, which looks up the user by email, verifies the submitted
password against the stored hash, and starts a session by writing
`session["user_id"]`. It also implements `GET /logout`, which clears the
session and returns the user to the landing page. Finally, the shared
navbar becomes session-aware so logged-in users see a "Sign out" link
instead of "Sign in" / "Get started". Together with Step 2 (Registration),
this completes the basic authentication loop that `/profile` (Step 4) and
the expense routes (Steps 7–9) will rely on.

## Depends on
- Step 1 — Database setup (`get_db()`, `users` table with `password_hash`,
  seeded demo user `demo@spendly.com` / `demo123`)
- Step 2 — Registration (`get_user_by_email(email)` in `database/db.py`,
  `app.secret_key` set, `session["user_id"]` convention established)

## Routes
- `POST /login` — validate email/password, look up user by email, verify
  password hash, set `session["user_id"]`, redirect to `/profile` — public
  (the existing `GET /login` stays; the route gains
  `methods=["GET", "POST"]`)
- `GET /logout` — clear the session and redirect to `/` (landing) —
  logged-in (safe to hit when logged out; it simply redirects)

## Database changes
No database changes. The `users` table already has `email` and
`password_hash`, and `get_user_by_email(email)` already exists in
`database/db.py`. Verified against `database/db.py`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — replace the hardcoded `action="/login"` with
    `action="{{ url_for('login') }}"`; optionally re-populate the email
    field with the submitted value on error (`value="{{ email or '' }}"`).
    The template already renders `{{ error }}`.
  - `templates/base.html` — make the navbar session-aware: when
    `session.user_id` is set, show a "Sign out" link to
    `url_for('logout')`; otherwise show the existing "Sign in" and
    "Get started" links

## Files to change
- `app.py` — change `/login` to accept `methods=["GET", "POST"]` and add
  POST handling; replace the `/logout` stub with a real implementation;
  import `check_password_hash` from `werkzeug.security`
- `templates/login.html` — `url_for()` form action, keep email on error
- `templates/base.html` — conditional navbar links based on session

## Files to create
None.

## New dependencies
No new dependencies. `check_password_hash` comes from `werkzeug.security`,
which is already pinned in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with
  `werkzeug.security.check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline SQL in `app.py` — reuse the existing `get_user_by_email()`
  helper from `database/db.py`
- Normalise the submitted email the same way registration does
  (`.strip().lower()`) before lookup
- Validate server-side: missing email or password re-renders
  `login.html` with an error and never touches the database
- Use one generic error message (e.g. "Invalid email or password.") for
  both unknown email and wrong password — never reveal which one failed
- On successful login, call `session.clear()` before setting
  `session["user_id"]` to avoid carrying over stale session data
- `/logout` must use `session.clear()` and `redirect(url_for("landing"))`
  — no raw string return
- If an already-logged-in user visits `GET /login`, redirect them to
  `/profile` instead of showing the form
- Redirecting to `/profile` is fine even though it is still a Step 4
  stub — do not implement `/profile` in this step
- Every internal link in templates uses `url_for()`

## Definition of done
- [ ] `GET /login` renders the sign-in form when logged out
- [ ] Logging in with `demo@spendly.com` / `demo123` redirects to
      `/profile` and the session contains the demo user's `user_id`
- [ ] Logging in with a freshly registered account works the same way
- [ ] Email lookup is case-insensitive (`DEMO@Spendly.com` logs in)
- [ ] A wrong password re-renders `login.html` with
      "Invalid email or password." and no session is created
- [ ] An unknown email shows the exact same error message
- [ ] Submitting with an empty email or password re-renders
      `login.html` with an error
- [ ] While logged in, the navbar shows "Sign out" and hides
      "Sign in" / "Get started"
- [ ] Visiting `GET /login` while logged in redirects to `/profile`
- [ ] Clicking "Sign out" clears the session, redirects to `/`, and the
      navbar shows "Sign in" / "Get started" again
- [ ] Visiting `/logout` while already logged out redirects to `/`
      without error
- [ ] `login.html` form action uses `url_for('login')` (no hardcoded URL)
- [ ] The app still starts and runs on port 5001 without errors
