# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user remove an expense they recorded by mistake. The
placeholder at `/expenses/<id>/delete` currently returns a raw string. This step
turns it into a two-part flow. GET shows a confirmation page with the expense's
details and a "Delete" button. POST deletes the row and redirects to `/profile`.
A GET request never deletes anything. Browsers, link prefetchers and `<img>` tags
on other sites can all trigger a GET without the user meaning to, so the delete
only happens on a POST from the confirmation form. As with Edit (Step 8), a user
may only delete their own expenses. Someone else's expense id, or an id that
doesn't exist, returns 404. Each row in the profile transaction table gets a
"Delete" link next to "Edit", and the edit form gets a "Delete" link too. This
completes create, read, update and delete for expenses.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with `PRAGMA foreign_keys = ON`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Profile page backend (`get_recent_transactions` returns `id` per row)
- Step 7: Add Expense (`add_expense.css` form-card styles)
- Step 8: Edit Expense (`get_expense_by_id`, the owner-only 404 pattern, the "Actions" column in `profile.html`)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the expense — logged-in (owner only)
- `POST /expenses/<int:id>/delete` — delete the expense, redirect to `/profile` — logged-in (owner only)

Access behaviour for both methods (same as `edit_expense`):
- Not logged in → redirect to `url_for("login")`
- Session user no longer exists → `session.clear()` and redirect to login
- Expense missing or owned by another user → `abort(404)`

Note: the CLAUDE.md route table lists this stub as `GET` only. This step adds
`POST` on purpose so that the delete happens on POST, not GET.

## Database changes
No database changes. No other table references `expenses`, so deleting a row
can't break a foreign key.

New query helper goes in `database/queries.py`, next to `update_expense`:
- `delete_expense(expense_id, user_id)` runs
  `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, and returns
  `True` if a row was deleted (`cursor.rowcount == 1`). It uses the same
  `try`/`finally: conn.close()` shape as `update_expense`.

The existing `get_expense_by_id(expense_id, user_id)` is reused for the GET
confirmation page and for the ownership check.

## Templates
- **Create:** `templates/delete_expense.html`
  - Extends `base.html`. Loads `css/add_expense.css` (shared form-card layout) and `css/delete_expense.css`
  - Title "Delete expense" and subtitle "This can't be undone."
  - A summary of the expense: date (`|date_fmt`), category, amount as `₹` with 2 decimals, and description (or "—" when NULL)
  - `<form method="POST" action="{{ url_for('delete_expense', id=expense.id) }}">`, with no input fields
  - Actions: a "Cancel" link to `url_for('profile')` and a "Delete Expense" submit button styled as a danger button
- **Modify:** `templates/profile.html`
  - In the existing "Actions" cell, add a "Delete" link after "Edit": `url_for('delete_expense', id=expense.id)`, with `aria-label` set to "Delete expense from <date>"
- **Modify:** `templates/edit_expense.html`
  - Add a low-emphasis "Delete this expense" link to `url_for('delete_expense', id=expense_id)` in the form actions area. It must not be a submit button inside the edit form

## Files to change
- `app.py`
  - Import `delete_expense` from `database.queries`. It has the same name as the route function, so import it under an alias, e.g. `from database.queries import delete_expense as delete_expense_row`, and keep the route's endpoint name `delete_expense`
  - Remove the placeholder `delete_expense` stub and the "Placeholder routes" section header, which will now be empty
  - Add `@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])` below `edit_expense`
  - GET: run the login and stale-session checks, then `get_expense_by_id(id, user_id)`, then `abort(404)` if it returns None. Render `delete_expense.html` with `expense`
  - POST: run the same checks, then call `delete_expense_row(id, user_id)`. If it returns `False` (the row vanished or isn't owned), `abort(404)`. Otherwise redirect to `url_for("profile")`
- `database/queries.py`: add `delete_expense`
- `templates/profile.html`: add the Delete link to the Actions cell
- `templates/edit_expense.html`: add the "Delete this expense" link
- `static/css/profile.css`: style the delete link next to the edit link (spacing, `var(--danger)` text colour, hover and `:focus-visible` states that match `.profile-edit`)
- `CLAUDE.md`: mark `GET/POST /expenses/<id>/delete` as implemented (Step 9)

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css`: styles for the expense summary and a `.btn-danger` button using `var(--danger)` / `var(--danger-light)`
- `tests/test_09-delete-expense.py` (written by the test-writer subagent)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only (`?` placeholders) — never f-strings or `%` in SQL
- Passwords hashed with werkzeug. This step doesn't touch passwords, so leave auth code alone
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=""` attributes, and no inline `onclick` / JS `confirm()`. The confirmation page does the confirming
- Every internal link uses `url_for()`
- DB logic stays in `database/queries.py`. The route only calls `get_expense_by_id` / `delete_expense`
- A GET request must never delete anything
- The `DELETE` must filter on both `id` and `user_id`. Never trust the URL id on its own
- Use `abort(404)` for missing or foreign expenses. Do not return an error string, and do not redirect
- After a successful delete, redirect (PRG). Never render a template on POST success
- Currency always displays as ₹
- Do not add a soft-delete column or a bulk-delete feature. That is out of scope

## Definition of done
- [ ] Visiting `/expenses/1/delete` while logged out redirects to `/login` (GET and POST), and no row is deleted
- [ ] As the demo user, each row in the profile transaction table shows both "Edit" and "Delete" links
- [ ] Clicking "Delete" opens `/expenses/<id>/delete` and shows that expense's date, category, amount (₹, 2 decimals) and description
- [ ] Loading the confirmation page (GET) does not remove the expense. Reloading `/profile` still shows it
- [ ] Clicking "Cancel" on the confirmation page returns to `/profile` with the expense still present
- [ ] Clicking "Delete Expense" redirects to `/profile`. The row is gone, the transaction count drops by one, and the total and category breakdown update
- [ ] Deleting a user's only expense in a category removes that category from the breakdown
- [ ] POSTing to the same delete URL again (after it's gone) returns 404
- [ ] Visiting `/expenses/99999/delete` (an id that doesn't exist) returns 404 for GET and POST
- [ ] Logged in as a second user, GET and POST to the demo user's expense id both return 404, and the demo user's row still exists
- [ ] The edit page (`/expenses/<id>/edit`) shows a "Delete this expense" link that opens the confirmation page
- [ ] The add (Step 7) and edit (Step 8) flows still work, and all existing tests pass under `pytest`
