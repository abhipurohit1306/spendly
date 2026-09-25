"""Tests for spec 06: date filter for the profile page.

Derived from .claude/specs/06-date-filter-profile-page.md, not from the
implementation. Covers:
- The pure helpers `parse_date_range` and `date_presets` in app.py
- The optional start_date/end_date filtering added to the query helpers
  in database/queries.py
- The filtered GET /profile route: auth guard, the Definition-of-done
  figures for the seeded demo user, validation errors, form/preset
  state, per-user isolation, and read-only behaviour
"""

import re
from datetime import date as real_date

import pytest

import app as app_module
from app import date_presets, parse_date_range
from database.db import create_user, get_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_USER_ID = 1

INVALID_DATE_MSG = "Please enter valid dates."
REVERSED_RANGE_MSG = "Start date must be on or before end date."
EMPTY_RANGE_MSG = "No expenses in this date range."

# Full, unfiltered totals for the seeded demo user (8 expenses).
FULL_TOTAL = "300.44"
FULL_COUNT = 8


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


class FrozenDate(real_date):
    """A `date` stand-in whose `today()` always returns 2026-09-25, so
    preset ranges are deterministic regardless of when the suite runs."""

    @classmethod
    def today(cls):
        return cls(2026, 9, 25)


# ------------------------------------------------------------------ #
# parse_date_range — pure function, no Flask/DB needed                #
# ------------------------------------------------------------------ #

def test_parse_date_range_missing_params_is_unfiltered():
    assert parse_date_range({}) == (None, None, None)


def test_parse_date_range_empty_strings_treated_as_no_bound():
    args = {"start_date": "", "end_date": ""}
    assert parse_date_range(args) == (None, None, None)


def test_parse_date_range_valid_range_returned_unchanged():
    args = {"start_date": "2026-09-01", "end_date": "2026-09-10"}
    assert parse_date_range(args) == ("2026-09-01", "2026-09-10", None)


def test_parse_date_range_start_only_is_open_ended():
    args = {"start_date": "2026-09-15"}
    assert parse_date_range(args) == ("2026-09-15", None, None)


def test_parse_date_range_end_only_is_open_ended():
    args = {"end_date": "2026-09-15"}
    assert parse_date_range(args) == (None, "2026-09-15", None)


def test_parse_date_range_equal_bounds_is_valid_inclusive_range():
    args = {"start_date": "2026-09-05", "end_date": "2026-09-05"}
    assert parse_date_range(args) == ("2026-09-05", "2026-09-05", None)


def test_parse_date_range_start_after_end_sets_reversed_error():
    args = {"start_date": "2026-09-20", "end_date": "2026-09-01"}
    start, end, error = parse_date_range(args)
    assert (start, end) == (None, None)
    assert error == REVERSED_RANGE_MSG


@pytest.mark.parametrize(
    "args",
    [
        {"start_date": "not-a-date"},
        {"end_date": "not-a-date"},
        {"start_date": "2026/09/01"},
        {"start_date": "09-01-2026"},
        {"start_date": "2026-02-30"},
    ],
)
def test_parse_date_range_unparseable_dates_set_invalid_error(args):
    start, end, error = parse_date_range(args)
    assert (start, end) == (None, None)
    assert error == INVALID_DATE_MSG


def test_parse_date_range_invalid_value_never_raises():
    # Spec: "It must not raise or 500" for unparseable input.
    parse_date_range({"start_date": "banana", "end_date": "also-not-a-date"})


# ------------------------------------------------------------------ #
# date_presets — pure function, fixed "today" values                  #
# ------------------------------------------------------------------ #

def test_date_presets_returns_five_labelled_ranges_in_order():
    presets = date_presets(real_date(2026, 9, 25))
    assert [p["label"] for p in presets] == [
        "This month",
        "Last 30 days",
        "Last 3 months",
        "Last 6 months",
        "All time",
    ]


def test_date_presets_this_month_spans_first_of_month_to_today():
    presets = {p["label"]: p for p in date_presets(real_date(2026, 9, 25))}
    assert presets["This month"]["start_date"] == "2026-09-01"
    assert presets["This month"]["end_date"] == "2026-09-25"


def test_date_presets_last_30_days_spans_29_days_back_to_today():
    presets = {p["label"]: p for p in date_presets(real_date(2026, 9, 25))}
    assert presets["Last 30 days"]["start_date"] == "2026-08-27"
    assert presets["Last 30 days"]["end_date"] == "2026-09-25"


def test_date_presets_last_3_and_6_months_same_day_n_months_back():
    presets = {p["label"]: p for p in date_presets(real_date(2026, 9, 25))}
    assert presets["Last 3 months"]["start_date"] == "2026-06-25"
    assert presets["Last 6 months"]["start_date"] == "2026-03-25"
    assert presets["Last 3 months"]["end_date"] == "2026-09-25"
    assert presets["Last 6 months"]["end_date"] == "2026-09-25"


def test_date_presets_month_ranges_clamp_to_shorter_month():
    # 31 May - 3 months -> 28 Feb (non-leap), per spec's own example.
    presets = {p["label"]: p for p in date_presets(real_date(2026, 5, 31))}
    assert presets["Last 3 months"]["start_date"] == "2026-02-28"


def test_date_presets_all_time_has_no_bounds():
    presets = {p["label"]: p for p in date_presets(real_date(2026, 9, 25))}
    assert presets["All time"] == {
        "label": "All time",
        "start_date": None,
        "end_date": None,
    }


# ------------------------------------------------------------------ #
# Query helpers — existing no-filter behaviour must be unchanged       #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_without_dates_unchanged(app):
    assert get_recent_transactions(DEMO_USER_ID) == get_recent_transactions(
        DEMO_USER_ID, start_date=None, end_date=None
    )


def test_get_summary_stats_without_dates_unchanged(app):
    assert get_summary_stats(DEMO_USER_ID) == get_summary_stats(
        DEMO_USER_ID, start_date=None, end_date=None
    )


def test_get_category_breakdown_without_dates_unchanged(app):
    assert get_category_breakdown(DEMO_USER_ID) == get_category_breakdown(
        DEMO_USER_ID, start_date=None, end_date=None
    )


# ------------------------------------------------------------------ #
# Query helpers — inclusive filtering                                 #
# ------------------------------------------------------------------ #

def test_get_summary_stats_sep1_to_sep10_matches_spec_figures(app):
    stats = get_summary_stats(DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-10")
    assert stats["transaction_count"] == 4
    assert stats["total_spent"] == pytest.approx(172.49)
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_sep11_to_sep20_matches_spec_figures(app):
    stats = get_summary_stats(DEMO_USER_ID, start_date="2026-09-11", end_date="2026-09-20")
    assert stats["transaction_count"] == 4
    assert stats["total_spent"] == pytest.approx(127.95)
    assert stats["top_category"] == "Shopping"


def test_get_summary_stats_single_day_bounds_are_inclusive(app):
    stats = get_summary_stats(DEMO_USER_ID, start_date="2026-09-05", end_date="2026-09-05")
    assert stats["transaction_count"] == 1
    assert stats["total_spent"] == pytest.approx(89.99)


def test_get_recent_transactions_single_day_returns_the_one_expense(app):
    transactions = get_recent_transactions(
        DEMO_USER_ID, start_date="2026-09-05", end_date="2026-09-05"
    )
    assert len(transactions) == 1
    assert transactions[0]["description"] == "Electricity bill"
    assert transactions[0]["amount"] == pytest.approx(89.99)


def test_open_ended_start_only_includes_everything_on_or_after(app):
    transactions = get_recent_transactions(DEMO_USER_ID, start_date="2026-09-15")
    assert len(transactions) == 2
    assert all(t["date"] >= "2026-09-15" for t in transactions)
    stats = get_summary_stats(DEMO_USER_ID, start_date="2026-09-15")
    assert stats["total_spent"] == pytest.approx(80.20)


def test_open_ended_end_only_includes_everything_on_or_before(app):
    transactions = get_recent_transactions(DEMO_USER_ID, end_date="2026-09-04")
    assert all(t["date"] <= "2026-09-04" for t in transactions)
    assert len(transactions) == 2


def test_no_matching_range_returns_empty_defaults(app):
    stats = get_summary_stats(DEMO_USER_ID, start_date="2025-01-01", end_date="2025-01-31")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    assert get_recent_transactions(DEMO_USER_ID, start_date="2025-01-01", end_date="2025-01-31") == []
    assert get_category_breakdown(DEMO_USER_ID, start_date="2025-01-01", end_date="2025-01-31") == []


def test_category_breakdown_filtered_categories_and_pct_sum_to_100(app):
    categories = get_category_breakdown(
        DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-10"
    )
    assert {c["name"] for c in categories} == {"Food", "Transport", "Bills", "Health"}
    assert sum(c["pct"] for c in categories) == 100


def test_get_recent_transactions_limit_still_applies_within_filtered_range(app):
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        [(DEMO_USER_ID, 1.0 + i, "Food", "2026-09-01", f"extra {i}") for i in range(15)],
    )
    conn.commit()
    conn.close()

    transactions = get_recent_transactions(
        DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-01"
    )
    assert len(transactions) == 10


def test_query_helpers_never_show_another_users_expenses(app):
    other_id = create_user("Other User", "other@spendly.com", "password123")
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (other_id, 500.00, "Shopping", "2026-09-05", "Other user's big buy"),
    )
    conn.commit()
    conn.close()

    demo_transactions = get_recent_transactions(
        DEMO_USER_ID, start_date="2026-09-05", end_date="2026-09-05"
    )
    assert [t["description"] for t in demo_transactions] == ["Electricity bill"]

    other_stats = get_summary_stats(other_id, start_date="2026-09-05", end_date="2026-09-05")
    assert other_stats["total_spent"] == pytest.approx(500.00)


def test_filtering_is_read_only_and_never_mutates_rows(app):
    conn = get_db()
    before = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM expenses"
    ).fetchone()
    conn.close()

    get_recent_transactions(DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-10")
    get_summary_stats(DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-10")
    get_category_breakdown(DEMO_USER_ID, start_date="2026-09-01", end_date="2026-09-10")

    conn = get_db()
    after = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM expenses"
    ).fetchone()
    conn.close()

    assert after["n"] == before["n"]
    assert after["total"] == pytest.approx(before["total"])


# ------------------------------------------------------------------ #
# /profile — auth guard applies with and without query params         #
# ------------------------------------------------------------------ #

def test_profile_logged_out_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_logged_out_with_query_params_still_redirects_to_login(client):
    response = client.get("/profile?start_date=2026-09-01&end_date=2026-09-10")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ #
# /profile — unfiltered baseline is unchanged from before this step   #
# ------------------------------------------------------------------ #

def test_profile_with_no_params_shows_same_data_as_before(client):
    login(client)
    response = client.get("/profile")
    data = response.data.decode()
    assert response.status_code == 200
    assert data.count('class="profile-row"') == FULL_COUNT
    assert f"₹{FULL_TOTAL}" in data
    assert "Across all categories" in data


# ------------------------------------------------------------------ #
# /profile — filtered ranges match the Definition-of-done figures     #
# ------------------------------------------------------------------ #

def test_profile_filter_sep1_to_sep10(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-01&end_date=2026-09-10")
    data = response.data.decode()
    assert response.status_code == 200
    assert data.count('class="profile-row"') == 4
    assert "₹172.49" in data
    assert re.search(r"Bills", data)


def test_profile_filter_sep11_to_sep20(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-11&end_date=2026-09-20")
    data = response.data.decode()
    assert response.status_code == 200
    assert data.count('class="profile-row"') == 4
    assert "₹127.95" in data


def test_profile_filter_single_day_proves_inclusive_bounds(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-05&end_date=2026-09-05")
    data = response.data.decode()
    assert response.status_code == 200
    assert data.count('class="profile-row"') == 1
    assert "Electricity bill" in data
    assert "₹89.99" in data


def test_profile_filter_open_ended_start(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-15")
    data = response.data.decode()
    assert response.status_code == 200
    assert data.count('class="profile-row"') == 2
    assert "₹80.20" in data


def test_profile_filter_no_matches_shows_empty_states_and_no_error(client):
    login(client)
    response = client.get("/profile?start_date=2025-01-01&end_date=2025-01-31")
    data = response.data.decode()
    assert response.status_code == 200
    assert "₹0.00" in data
    assert EMPTY_RANGE_MSG in data
    assert INVALID_DATE_MSG not in data
    assert REVERSED_RANGE_MSG not in data


def test_profile_reversed_range_returns_200_with_error_and_unfiltered_data(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-20&end_date=2026-09-01")
    data = response.data.decode()
    assert response.status_code == 200
    assert REVERSED_RANGE_MSG in data
    assert data.count('class="profile-row"') == FULL_COUNT
    assert f"₹{FULL_TOTAL}" in data


def test_profile_invalid_date_returns_200_with_error_and_unfiltered_data(client):
    login(client)
    response = client.get("/profile?start_date=not-a-date")
    data = response.data.decode()
    assert response.status_code == 200
    assert INVALID_DATE_MSG in data
    assert data.count('class="profile-row"') == FULL_COUNT
    assert f"₹{FULL_TOTAL}" in data


def test_profile_does_not_500_on_invalid_input(client):
    login(client)
    response = client.get("/profile?start_date=banana&end_date=also-bad")
    assert response.status_code == 200


# ------------------------------------------------------------------ #
# /profile — form state and range-aware sub-label                     #
# ------------------------------------------------------------------ #

def test_profile_form_retains_submitted_valid_dates(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-01&end_date=2026-09-10")
    data = response.data.decode()
    assert 'name="start_date"' in data and 'value="2026-09-01"' in data
    assert 'name="end_date"' in data and 'value="2026-09-10"' in data


def test_profile_sublabel_shows_active_range_when_both_bounds_set(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-02&end_date=2026-09-10")
    data = response.data.decode()
    assert "02 Sep 2026" in data
    assert "10 Sep 2026" in data
    assert "Across all categories" not in data


def test_profile_sublabel_open_start_reads_from_prefix(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-15")
    data = response.data.decode()
    assert "From 15 Sep 2026" in data


def test_profile_sublabel_open_end_reads_until_prefix(client):
    login(client)
    response = client.get("/profile?end_date=2026-09-04")
    data = response.data.decode()
    assert "Until 04 Sep 2026" in data


def test_profile_sublabel_default_text_when_unfiltered(client):
    login(client)
    response = client.get("/profile")
    data = response.data.decode()
    assert "Across all categories" in data


# ------------------------------------------------------------------ #
# /profile — Clear link                                               #
# ------------------------------------------------------------------ #

def test_profile_clear_link_absent_when_no_filter_active(client):
    login(client)
    response = client.get("/profile")
    assert b">Clear<" not in response.data


def test_profile_clear_link_present_and_targets_unfiltered_profile(client):
    login(client)
    response = client.get("/profile?start_date=2026-09-01&end_date=2026-09-10")
    data = response.data.decode()
    match = re.search(r'<a href="([^"]*)"[^>]*>Clear</a>', data)
    assert match is not None
    assert match.group(1) == "/profile"


# ------------------------------------------------------------------ #
# /profile — presets                                                  #
# ------------------------------------------------------------------ #

def test_profile_all_time_preset_marked_active_when_unfiltered(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile")
    data = response.data.decode()
    assert re.search(r'aria-current="true">All time<', data)


def test_profile_this_month_preset_applies_range_and_is_marked_active(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile?start_date=2026-09-01&end_date=2026-09-25")
    data = response.data.decode()
    assert re.search(r'aria-current="true">This month<', data)
    assert not re.search(r'aria-current="true">Last 30 days<', data)


def test_profile_last_30_days_preset_applies_range_and_is_marked_active(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile?start_date=2026-08-27&end_date=2026-09-25")
    data = response.data.decode()
    assert re.search(r'aria-current="true">Last 30 days<', data)
    assert not re.search(r'aria-current="true">This month<', data)


def test_profile_last_3_months_preset_applies_range_and_is_marked_active(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile?start_date=2026-06-25&end_date=2026-09-25")
    data = response.data.decode()
    assert re.search(r'aria-current="true">Last 3 months<', data)


def test_profile_last_6_months_preset_applies_range_and_is_marked_active(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile?start_date=2026-03-25&end_date=2026-09-25")
    data = response.data.decode()
    assert re.search(r'aria-current="true">Last 6 months<', data)


def test_profile_preset_links_are_url_for_generated_and_escape_ampersand(client, monkeypatch):
    monkeypatch.setattr(app_module, "date", FrozenDate)
    login(client)
    response = client.get("/profile")
    data = response.data.decode()
    # url_for()-built hrefs with two query params render '&' as '&amp;'.
    assert "start_date=2026-09-01&amp;end_date=2026-09-25" in data
    assert "start_date=2026-09-01&end_date=2026-09-25" not in data


# ------------------------------------------------------------------ #
# /profile — per-user isolation under a filter                        #
# ------------------------------------------------------------------ #

def test_profile_filter_never_leaks_another_users_expenses(client):
    other_id = create_user("Other User", "other@spendly.com", "password123")
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (other_id, 500.00, "Shopping", "2026-09-05", "Other user's big buy"),
    )
    conn.commit()
    conn.close()

    login(client)
    response = client.get("/profile?start_date=2026-09-05&end_date=2026-09-05")
    data = response.data.decode()
    assert "Electricity bill" in data
    assert "Other user's big buy" not in data
    assert "₹500.00" not in data
