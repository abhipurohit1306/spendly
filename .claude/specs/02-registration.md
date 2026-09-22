# Spec: Registration

## Overview
This feature implements real account creation for Spendly. The `/register`
page and template already exist but only render a static form — submitting
it does nothing yet. This step wires the form up to `POST /register`, which
validates the input, hashes the password, inserts a new row into the
`users` table, and starts a logged-in session for the new user. This is the
first authentication behavior in the app and the foundation that `/login`,
`/logout`, and `/profile` will build on in later steps.

## Depends on
Step 1 — Database setup. Requires `get_db()`, `init_db()`, and the `users`
table (with `password_hash`) already in place in `database/db.py`.

## Routes
- `POST /register` — validate submitted name/email/password, hash the
  password, create the user, start their session, redirect — public
  (the existing `GET /register` stays as-is; the route gains
  `methods=["GET", "POST"]`)

## Database changes
No database changes. The `users` table from Step 1 already has the
columns this feature needs (`name`, `email`, `password_hash`). Verified
against `database/db.py`.

## Templates
- **Create:** none
- **Modify:** none — `templates/register.html` already posts to `/register`
  and already renders `{{ error }}` when passed from the route, so no
  template changes are required

## Files to change
- `database/db.py` — add `get_user_by_email(email)` and
  `create_user(name, email, password)` helper functions (parameterized
  queries, password hashed with `werkzeug.security.generate_password_hash`
  before insert)
- `app.py` — change `/register` to accept `methods=["GET", "POST"]`;
  on `POST`, validate input, call the new `db.py` helpers, set
  `app.secret_key` for session support, write `session["user_id"]` on
  success, and redirect to `/profile`; on validation failure or duplicate
  email, re-render `register.html` with an `error` message

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`) — never store
  plaintext passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access (including the new duplicate-email check and insert)
  lives in `database/db.py`, never inline SQL in `app.py`
- Validate `name`, `email`, and `password` server-side even though the
  form has client-side `required` attributes — never trust client input
- Check for an existing email before insert and surface a friendly error
  on the form rather than letting a raw `sqlite3.IntegrityError` propagate
- Redirecting to `/profile` after registration is fine even though
  `/profile` is still a Step 4 stub — do not implement `/profile` itself
  as part of this step

## Definition of done
- [ ] `GET /register` still renders the form exactly as before
- [ ] Submitting the form with valid, unique data creates one new row in
      `users` with a hashed (not plaintext) password
- [ ] Submitting with an email that's already registered re-renders
      `register.html` with an error and does not create a duplicate row
- [ ] Submitting with a missing name, email, or password re-renders
      `register.html` with an error and never reaches the database
- [ ] A successful registration redirects away from `/register` and the
      session contains the new user's `user_id`
- [ ] The app still starts and runs on port 5001 without errors
