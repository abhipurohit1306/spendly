# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user correct an existing expense. The placeholder at
`/expenses/<id>/edit` currently returns a raw string. This step turns it into a
full GET + POST handler. GET shows a form pre-filled with the expense's current
values. POST validates the submission with the same rules as Add Expense
(`parse_expense_form`), updates the row, and redirects to `/profile`. A user may
only view or edit their own expenses. Someone else's expense id, or an id that
doesn't exist, returns 404, so other users' ids aren't exposed. Each row in the
profile transaction table gets an "Edit" link so the feature can be reached from
the UI.

## Depends on
- Step 1: Database setup (`expenses` table with `id`, `user_id`, `amount`, `category`, `date`, `description`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Profile page backend (`get_recent_transactions` already returns `id` per row)
- Step 7: Add Expense (`parse_expense_form`, `EXPENSE_CATEGORIES`, `add_expense.html` / `add_expense.css` form styles)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense — logged-in (owner only)
- `POST /expenses/<int:id>/edit` — validate and save changes, redirect to `/profile` — logged-in (owner only)

Access behaviour for both methods:
- Not logged in → redirect to `url_for("login")`
- Session user no longer exists → `session.clear()` and redirect to login (same as `add_expense`)
- Expense missing or owned by another user → `abort(404)`

## Database changes
No database changes. The existing `expenses` table already has every column this step needs.

New query helpers go in `database/queries.py`, next to `insert_expense`, because
that is where expense query helpers already live:
- `get_expense_by_id(expense_id, user_id)` returns a dict with `id`, `amount`,
  `category`, `date` and `description`, or `None`. It uses
  `WHERE id = ? AND user_id = ?`, so the ownership check happens in SQL.
- `update_expense(expense_id, user_id, amount, category, date, description=None)`
  runs `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
  WHERE id = ? AND user_id = ?`, commits, and returns `True` if a row was changed
  (`cursor.rowcount == 1`).

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html` and loads `css/add_expense.css`, so the two forms share one stylesheet and look the same
  - Title "Edit expense" and subtitle "Update the details of this expense"
  - `<form method="POST" action="{{ url_for('edit_expense', id=expense_id) }}">`
  - Same four fields and attributes as `add_expense.html`: `amount`, `category`, `date`, `description`
  - Values come from `form` (the stored expense on GET, the submitted `request.form` on a failed POST)
  - Shows an error block with `role="alert"` when `error` is set
  - Actions: a "Cancel" link to `url_for('profile')` and a "Save Changes" submit button
- **Modify:** `templates/profile.html`
  - Add a final, visually labelled "Actions" column to the transaction table
  - Each row gets an "Edit" link: `url_for('edit_expense', id=expense.id)`, with `aria-label` set to "Edit expense from <date>"

## Files to change
- `app.py`
  - Import `get_expense_by_id` and `update_expense` from `database.queries`
  - Import `abort` from `flask`
  - Replace the `edit_expense` placeholder with `@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])`
  - GET renders `edit_expense.html` with `form` set to the expense values (amount formatted to 2 decimal places, and `description` as `""` when it is NULL)
  - POST runs `parse_expense_form(request.form)`. On error it re-renders with the submitted values and the message. On success it calls `update_expense` and redirects to `url_for("profile")`
  - Update the `parse_expense_form` docstring so it no longer says "add-expense" only
- `database/queries.py`: add `get_expense_by_id` and `update_expense`
- `templates/profile.html`: add the Edit link column
- `static/css/profile.css`: style the actions column and edit link using the existing CSS variables
- `CLAUDE.md`: mark `GET/POST /expenses/<id>/edit` as implemented (Step 8)

## Files to create
- `templates/edit_expense.html`
- `tests/test_08-edit-expense.py` (written by the test-writer subagent)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only (`?` placeholders) — never f-strings or `%` in SQL
- Passwords hashed with werkzeug. This step doesn't touch passwords, so leave auth code alone
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=""` attributes
- Every internal link uses `url_for()`
- Reuse `parse_expense_form` and `EXPENSE_CATEGORIES`. Do not duplicate validation logic
- Both the `SELECT` and the `UPDATE` must filter on `user_id`. Never trust the URL id on its own
- Use `abort(404)` for missing or foreign expenses. Do not return an error string, and do not redirect
- Never change `user_id` or `created_at` in the UPDATE
- After a successful save, redirect. Never render the form again (the PRG pattern)
- Currency always displays as ₹
- Do not implement the Step 9 delete route

## Definition of done
- [ ] Visiting `/expenses/1/edit` while logged out redirects to `/login` (GET and POST)
- [ ] As the demo user, clicking "Edit" on a row in the profile transaction table opens `/expenses/<id>/edit`
- [ ] The edit form shows that expense's current amount, category, date and description
- [ ] Changing the amount and category, then saving, redirects to `/profile`. The row shows the new values, and the summary stats and category breakdown reflect the change
- [ ] Clearing the description and saving stores it as NULL, with no error
- [ ] Submitting an empty, zero, negative or non-numeric amount re-renders the form with an error and keeps the entered values. The DB row is unchanged
- [ ] Submitting an invalid category or date re-renders the form with an error. The DB row is unchanged
- [ ] Visiting `/expenses/99999/edit` (an id that doesn't exist) returns 404
- [ ] Logged in as a second user, GET and POST to the demo user's expense id both return 404, and the demo user's row is unchanged
- [ ] "Cancel" on the edit form goes back to `/profile` without changing anything
- [ ] The add-expense flow (Step 7) still works, and all existing tests pass under `pytest`
