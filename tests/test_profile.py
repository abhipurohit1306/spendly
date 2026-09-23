import re
from pathlib import Path

import pytest

from app import build_profile_summary, date_fmt, initials

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "profile.html"


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


@pytest.fixture
def profile_page(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    return client.get("/profile")


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_returns_200_when_logged_in(profile_page):
    assert profile_page.status_code == 200


def test_profile_shows_user_card(profile_page):
    data = profile_page.data
    assert b"Demo User" in data
    assert b"demo@spendly.com" in data
    assert b">DU<" in data
    assert b"Member since" in data
    assert b"September 2026" in data


def test_profile_shows_summary_stats(profile_page):
    data = profile_page.data
    assert "₹300.44".encode() in data
    assert re.search(rb'profile-stat-value[^>]*>8<', data)
    assert re.search(rb'profile-stat-value">Bills<', data)


def test_profile_shows_transaction_rows(profile_page):
    data = profile_page.data
    assert data.count(b'class="profile-row"') >= 3
    assert b"Electricity bill" in data
    assert b"02 Sep 2026" in data
    assert "₹89.99".encode() in data


def test_profile_shows_category_breakdown(profile_page):
    data = profile_page.data
    assert data.count(b"<progress") >= 3
    assert b"profile-bar--bills" in data
    assert b'value="30"' in data


def test_profile_badges_use_css_classes(profile_page):
    data = profile_page.data
    assert b"profile-badge--food" in data
    assert b'style="' not in data


def test_profile_template_has_no_hex_or_inline_styles():
    text = TEMPLATE.read_text()
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", text) is None
    assert "<style" not in text
    assert 'style="' not in text


def test_profile_navbar_shows_logged_in_state(profile_page):
    data = profile_page.data
    assert b'class="nav-user"' in data
    assert b"Sign out" in data
    assert b"Get started" not in data


def test_profile_links_add_expense_and_stylesheet(profile_page):
    data = profile_page.data
    assert b'href="/expenses/add"' in data
    assert b"css/profile.css" in data


def test_build_profile_summary_seed_data():
    from app import PROFILE_EXPENSES

    summary = build_profile_summary(PROFILE_EXPENSES)
    assert summary["total_spent"] == pytest.approx(300.44)
    assert summary["transaction_count"] == 8
    assert summary["top_category"] == "Bills"
    totals = [item["total"] for item in summary["categories"]]
    assert totals == sorted(totals, reverse=True)
    assert len(summary["categories"]) == 7
    food = next(c for c in summary["categories"] if c["category"] == "Food")
    assert food["total"] == pytest.approx(45.25)


def test_build_profile_summary_empty():
    summary = build_profile_summary([])
    assert summary == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": None,
        "categories": [],
    }


def test_date_fmt_filter():
    assert date_fmt("2026-09-02") == "02 Sep 2026"
    assert date_fmt("2026-09-01", "%B %Y") == "September 2026"
    assert date_fmt("not-a-date") == "not-a-date"


def test_initials_filter():
    assert initials("Demo User") == "DU"
    assert initials("asha") == "A"
    assert initials("Mary Ann Lee") == "ML"
    assert initials("") == "?"
    assert initials(None) == "?"
