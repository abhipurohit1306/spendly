# Spec: Date Filter for Profile Page

## Overview
This feature adds a date range filter to the profile page. Step 5 connected
every section of `/profile` to live data, but each section always covers the
user's full history. This step lets a logged-in user choose a start date and
an end date, or pick a quick preset such as "This month". The summary stats,
the transaction history and the category breakdown then show only expenses
in that range. The filter uses GET query parameters
(`/profile?start_date=2026-09-01&end_date=2026-09-10`), so a filtered view
can be bookmarked and survives a page refresh. It needs no new route and no
schema change. It is the last read-side improvement to the profile page
before the expense write routes (Steps 7–9) are built.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]` guards `/profile`)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`)
- Step 5: Profile page backend (`database/queries.py` helpers wired into `/profile`)

## Routes
No new routes. The existing route is modified:
- `GET /profile` accepts two optional query parameters, `start_date` and
  `end_date` (both `YYYY-MM-DD`). It passes them to the query helpers and
  renders the filtered page. Access: logged-in (unauthenticated users are
  still redirected to `/login`).

## Database changes
No database changes. `expenses.date` is already `TEXT NOT NULL` in
`YYYY-MM-DD` format (verified against `database/db.py`). ISO dates sort
lexically, so plain `>=` / `<=` comparisons on the column filter correctly.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar between the profile header and the `profile-top` block:
    - A `<form method="get" action="{{ url_for('profile') }}">` containing
      two `<input type="date">` fields named `start_date` and `end_date`,
      each with a visible `<label>`, plus an "Apply" submit button
    - Inputs are pre-filled with the currently active dates so the filter
      state persists after submit
    - A "Clear" link to `url_for('profile')` (no params), shown only when a
      filter is active
    - Preset links built with `url_for('profile', start_date=..., end_date=...)`:
      "This month", "Last 30 days", "Last 3 months", "Last 6 months",
      "All time". The preset matching the
      current range gets an active modifier class and `aria-current="true"`
  - When the filter is invalid, show an inline error message inside the filter bar
  - Change the "Total spent" sub-label from "Across all categories" to the
    active range (e.g. "02 Sep 2026 – 10 Sep 2026", using the existing
    `date_fmt` filter) when a filter is active; keep "Across all categories"
    otherwise. Open-ended ranges read "From 02 Sep 2026" / "Until 10 Sep 2026"
  - Empty-state copy changes when a filter is active, e.g. "No expenses in
    this date range." instead of "No expenses yet."

## Files to change
- `database/queries.py`: add optional `start_date=None, end_date=None`
  keyword arguments to `get_recent_transactions`, `get_summary_stats` and
  `get_category_breakdown`, and apply them to every `WHERE` clause.
  Existing callers with no dates must behave exactly as before
- `app.py`:
  - In `profile()`, read `start_date` / `end_date` from `request.args`,
    validate them through a small helper, and pass the valid values to all
    three query helpers. Pass `start_date`, `end_date`, `filter_error` and
    `presets` to the template
  - Add a module-level helper `parse_date_range(args)` that returns
    `(start_date, end_date, error)`. Add `date_presets(today)`, which
    returns the preset ranges as a list of `{label, start_date, end_date}`
    dicts. Both are pure functions with no DB access
- `templates/profile.html`: filter bar, range-aware sub-label, filtered
  empty states (see Templates)
- `static/css/profile.css`: styles for the filter bar, date inputs, preset
  links (with active state), and the inline error
- `CLAUDE.md`: update the `GET /profile` row of the routes table to mention
  the date filter

## Files to create
- `tests/test_date_filter.py`: tests for the filtered query helpers and the
  filtered `/profile` route (see Definition of done)

## New dependencies
No new dependencies. Date parsing uses the standard library `datetime`,
which `app.py` already imports.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only. Dates are always bound with `?` and never
  formatted into SQL. Prefer a static clause such as
  `AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)` over
  building SQL strings conditionally
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables and never hardcode hex values. Reuse the tokens in
  `static/css/style.css` (`--accent`, `--border`, `--danger`,
  `--danger-light`, `--radius-sm`, etc.)
- All templates extend `base.html`
- Page-specific styles go in `static/css/profile.css`, never in inline
  `style` attributes or `<style>` tags
- Every internal link and form action uses `url_for()`, including the
  preset links and the "Clear" link
- No DB logic in `app.py`. All filtering happens in `database/queries.py`
- No JavaScript is needed. The filter must work as a plain HTML GET form
- Both bounds are **inclusive**: an expense dated exactly on `start_date`
  or `end_date` is included
- Either bound may be supplied alone (open-ended range)
- Validation (in `parse_date_range`):
  - A value that is empty or missing is treated as "no bound"
  - A value that does not parse as `YYYY-MM-DD` (via
    `datetime.strptime`) sets `filter_error` to "Please enter valid dates."
    and the page renders **unfiltered**. It must not raise or 500
  - If `start_date` is later than `end_date`, `filter_error` is set to
    "Start date must be on or before end date." and the page renders
    **unfiltered**
- `summary`, `expenses` and `categories` must all use the same range. The
  sections must never disagree
- With a filter that matches nothing, all helpers return their existing
  empty values (zeros, "—", `[]`) and the page shows its empty states
- Category `pct` values must still sum to 100 within the filtered range
- `get_recent_transactions` keeps its `limit=10` inside the filtered range
- Presets are computed from `date.today()` in the route and passed to
  `date_presets()`, so tests can call `date_presets()` with a fixed date:
  - This month: first day of the current month → today
  - Last 30 days: today − 29 days → today
  - Last 3 months / Last 6 months: same day 3 / 6 calendar months ago
    (clamped to the month's last day, e.g. 31 May → 28 Feb) → today
  - All time: no params

## Definition of done
All figures below use the seeded demo user (`demo@spendly.com` / `demo123`).
- [ ] `GET /profile` with no query params shows exactly the same data as
      before this step (8 transactions, full totals)
- [ ] `/profile` while logged out still redirects to `/login`, including
      when query params are present
- [ ] `/profile?start_date=2026-09-01&end_date=2026-09-10` shows 4
      transactions, total spent ₹172.49 and top category "Bills". The
      breakdown lists only Food, Transport, Bills and Health, and its
      percentages add up to 100
- [ ] `/profile?start_date=2026-09-11&end_date=2026-09-20` shows 4
      transactions, total spent ₹127.95 and top category "Shopping"
- [ ] `/profile?start_date=2026-09-05&end_date=2026-09-05` shows exactly
      1 transaction (Electricity bill, ₹89.99), which proves the bounds
      are inclusive
- [ ] `/profile?start_date=2026-09-15` (open-ended) shows only the 2
      expenses dated on or after 15 Sep (total ₹80.20)
- [ ] `/profile?start_date=2025-01-01&end_date=2025-01-31` shows ₹0.00, 0
      transactions, top category "—" and the "No expenses in this date
      range." empty states with no error
- [ ] `/profile?start_date=2026-09-20&end_date=2026-09-01` returns 200,
      shows "Start date must be on or before end date." and renders
      the unfiltered data
- [ ] `/profile?start_date=not-a-date` returns 200, shows "Please enter
      valid dates." and renders the unfiltered data
- [ ] After submitting the filter form, the date inputs keep the applied
      values, and the "Total spent" sub-label shows the active range
- [ ] The "Clear" link appears only when a filter is active and returns
      to the unfiltered `/profile`
- [ ] Clicking "This month", "Last 30 days", "Last 3 months" and
      "Last 6 months" applies the correct range,
      and the matching preset is visually marked active
- [ ] Filtering by one user's range never shows another user's expenses
- [ ] No hex colour values or inline styles appear in `profile.html`, and
      new CSS lives in `profile.css` and uses only CSS variables
- [ ] `pytest` passes, including the new `tests/test_date_filter.py`
- [ ] The app still starts and runs on port 5001 without errors
