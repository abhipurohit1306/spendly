import pytest

from database.db import create_user, get_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

DEMO_USER_ID = 1
DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


@pytest.fixture
def empty_user_id(app):
    """A freshly registered user with no expenses."""
    return create_user("Empty User", "empty@spendly.com", "password123")


@pytest.fixture
def demo_page(client):
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    return client.get("/profile")


# ------------------------------------------------------------------ #
# get_user_by_id                                                      #
# ------------------------------------------------------------------ #

def test_get_user_by_id_returns_user(app):
    user = get_user_by_id(DEMO_USER_ID)
    assert user["name"] == "Demo User"
    assert user["email"] == DEMO_EMAIL
    assert user["member_since"]
    assert "password_hash" not in user


def test_get_user_by_id_missing_returns_none(app):
    assert get_user_by_id(9999) is None


# ------------------------------------------------------------------ #
# Transaction history                                                 #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_newest_first(app):
    transactions = get_recent_transactions(DEMO_USER_ID)
    assert len(transactions) == 8
    for item in transactions:
        for key in ("date", "description", "category", "amount"):
            assert key in item
    dates = [item["date"] for item in transactions]
    assert dates == sorted(dates, reverse=True)
    assert transactions[0]["description"] == "Birthday gift"
    assert transactions[0]["date"] == "2026-09-20"
    assert transactions[-1]["description"] == "Coffee and bagel"
    assert transactions[-1]["date"] == "2026-09-02"


def test_get_recent_transactions_respects_limit(app):
    transactions = get_recent_transactions(DEMO_USER_ID, limit=3)
    assert len(transactions) == 3
    assert transactions[0]["description"] == "Birthday gift"


def test_get_recent_transactions_no_expenses_returns_empty(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


def test_get_recent_transactions_isolated_per_user(empty_user_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (empty_user_id, 99.00, "Food", "2026-09-22", "Other user's lunch"),
    )
    conn.commit()
    conn.close()

    other = get_recent_transactions(empty_user_id)
    assert [item["description"] for item in other] == ["Other user's lunch"]

    demo = get_recent_transactions(DEMO_USER_ID)
    assert len(demo) == 8
    assert "Other user's lunch" not in [item["description"] for item in demo]


# ------------------------------------------------------------------ #
# Summary stats                                                       #
# ------------------------------------------------------------------ #

def test_get_summary_stats_demo_user(app):
    stats = get_summary_stats(DEMO_USER_ID)
    assert stats["total_spent"] == pytest.approx(300.44)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_empty_user(empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_summary_stats_isolated_per_user(empty_user_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (empty_user_id, 999.99, "Shopping", "2026-09-21", "Other user's buy"),
    )
    conn.commit()
    conn.close()

    demo = get_summary_stats(DEMO_USER_ID)
    assert demo["total_spent"] == pytest.approx(300.44)
    assert demo["transaction_count"] == 8
    assert demo["top_category"] == "Bills"

    other = get_summary_stats(empty_user_id)
    assert other["total_spent"] == pytest.approx(999.99)
    assert other["transaction_count"] == 1
    assert other["top_category"] == "Shopping"


# ------------------------------------------------------------------ #
# Category breakdown                                                  #
# ------------------------------------------------------------------ #

def test_category_breakdown_demo_user(app):
    categories = get_category_breakdown(DEMO_USER_ID)
    assert len(categories) == 7
    assert [c["name"] for c in categories][:2] == ["Bills", "Shopping"]
    amounts = [c["amount"] for c in categories]
    assert amounts == sorted(amounts, reverse=True)
    food = next(c for c in categories if c["name"] == "Food")
    assert food["amount"] == pytest.approx(45.25)
    assert all(isinstance(c["pct"], int) for c in categories)
    assert sum(c["pct"] for c in categories) == 100


def test_category_breakdown_empty_user(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


def test_category_breakdown_rounding_adjusts_largest(app):
    user_id = create_user("Even Split", "even@spendly.com", "password123")
    conn = get_db()
    for category in ("Food", "Bills", "Health"):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, 10.0, category, "2026-09-01", "test"),
        )
    conn.commit()
    conn.close()

    categories = get_category_breakdown(user_id)
    assert sorted(c["pct"] for c in categories) == [33, 33, 34]
    assert categories[0]["pct"] == 34
    assert sum(c["pct"] for c in categories) == 100


# ------------------------------------------------------------------ #
# /profile route                                                      #
# ------------------------------------------------------------------ #

def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_shows_demo_user_data(demo_page):
    data = demo_page.data.decode()
    assert demo_page.status_code == 200
    assert "Demo User" in data
    assert DEMO_EMAIL in data
    assert "₹" in data
    assert "₹300.44" in data
    assert 'profile-stat-value profile-num">8<' in data
    assert 'profile-stat-value">Bills<' in data


def test_profile_transactions_newest_first(demo_page):
    data = demo_page.data.decode()
    assert data.count('class="profile-row"') == 8
    assert data.index("20 Sep 2026") < data.index("02 Sep 2026")


def test_profile_breakdown_has_all_categories(demo_page):
    data = demo_page.data.decode()
    assert data.count("<progress") == 7


def test_profile_new_user_empty_state(client):
    client.post(
        "/register",
        data={"name": "New User", "email": "new@spendly.com", "password": "password123"},
    )
    response = client.get("/profile")
    data = response.data.decode()
    assert response.status_code == 200
    assert "New User" in data
    assert "₹0.00" in data
    assert 'profile-stat-value profile-num">0<' in data
    assert "No expenses yet" in data
    assert "<progress" not in data


def test_profile_stale_session_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
