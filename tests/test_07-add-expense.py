"""
Tests for Step 7 — Add Expense (spec: .claude/specs/07-add-expense.md).

Derived from the spec's routes, validation rules, templates section and
"Tests to write" / "Definition of done" lists — not from reading app.py's
implementation logic.
"""

import re
from datetime import date

import pytest

from database.db import create_user, get_db
from database.queries import insert_expense

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_USER_ID = 1

REQUIRED_CATEGORIES = {
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
}


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def valid_payload(**overrides):
    payload = {
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20",
        "description": "Lunch",
    }
    payload.update(overrides)
    return payload


def option_values(html):
    """Return the non-empty `value="..."` attributes of every <option> tag."""
    return [v for v in re.findall(r'<option[^>]*value="([^"]*)"', html) if v]


def has_alert(html):
    """A structural signal that an error message was rendered, without
    pinning the test to exact wording (spec does not fix error text)."""
    return 'role="alert"' in html


def fetch_expense(app, user_id, description):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND description = ?",
            (user_id, description),
        ).fetchone()
        conn.close()
        return row


def count_expenses(app, user_id):
    with app.app_context():
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
        conn.close()
        return count


# ------------------------------------------------------------------ #
# Unit tests: insert_expense (spec "Tests to write" -> Unit tests)     #
# ------------------------------------------------------------------ #

def test_insert_expense_inserts_row_that_can_be_queried_back(app):
    with app.app_context():
        insert_expense(
            DEMO_USER_ID,
            amount=50.0,
            category="Food",
            date="2026-03-20",
            description="Lunch",
        )
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND description = ?",
            (DEMO_USER_ID, "Lunch"),
        ).fetchone()
        conn.close()

    assert row is not None
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"


def test_insert_expense_with_no_description_stores_null(app):
    with app.app_context():
        insert_expense(
            DEMO_USER_ID,
            amount=12.0,
            category="Other",
            date="2026-03-21",
            description=None,
        )
        conn = get_db()
        row = conn.execute(
            "SELECT description FROM expenses WHERE user_id = ? AND amount = 12.0",
            (DEMO_USER_ID,),
        ).fetchone()
        conn.close()

    assert row is not None
    assert row["description"] is None


# ------------------------------------------------------------------ #
# GET /expenses/add                                                    #
# ------------------------------------------------------------------ #

def test_get_add_expense_unauthenticated_redirects_to_login(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_get_add_expense_authenticated_returns_200(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/expenses/add")
    assert response.status_code == 200


def test_get_add_expense_contains_post_form(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/expenses/add")
    body = response.data.decode()
    assert "<form" in body
    assert 'method="POST"' in body or "method='POST'" in body


def test_get_add_expense_category_select_has_exactly_the_7_options(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/expenses/add")
    body = response.data.decode()
    assert "<select" in body
    values = option_values(body)
    assert set(values) == REQUIRED_CATEGORIES
    assert len(values) == 7


def test_get_add_expense_amount_field_has_required_attributes(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/expenses/add").data.decode()
    assert 'name="amount"' in body
    assert 'type="number"' in body
    assert 'step="0.01"' in body
    assert 'min="0.01"' in body


def test_get_add_expense_date_field_defaults_to_today_and_is_required(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/expenses/add").data.decode()
    assert 'name="date"' in body
    assert 'type="date"' in body
    today = date.today().isoformat()
    assert f'value="{today}"' in body


def test_get_add_expense_description_field_optional_with_200_char_limit(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/expenses/add").data.decode()
    assert 'name="description"' in body
    assert 'maxlength="200"' in body


def test_get_add_expense_has_cancel_link_back_to_profile(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/expenses/add").data.decode()
    assert 'href="/profile"' in body


# ------------------------------------------------------------------ #
# POST /expenses/add — auth                                            #
# ------------------------------------------------------------------ #

def test_post_add_expense_unauthenticated_redirects_to_login(client):
    response = client.post("/expenses/add", data=valid_payload())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_post_add_expense_unauthenticated_does_not_insert_row(client, app):
    before = count_expenses(app, DEMO_USER_ID)
    client.post("/expenses/add", data=valid_payload())
    assert count_expenses(app, DEMO_USER_ID) == before


# ------------------------------------------------------------------ #
# POST /expenses/add — happy path                                      #
# ------------------------------------------------------------------ #

def test_post_add_expense_valid_data_redirects_to_profile(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.post("/expenses/add", data=valid_payload())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_post_add_expense_valid_data_inserts_row_for_current_user(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    client.post("/expenses/add", data=valid_payload(description="Unique lunch marker"))

    row = fetch_expense(app, DEMO_USER_ID, "Unique lunch marker")
    assert row is not None
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"


def test_post_add_expense_new_expense_appears_in_profile_transaction_list(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    client.post(
        "/expenses/add", data=valid_payload(description="Traceable description xyz")
    )
    profile_body = client.get("/profile").data.decode()
    assert "Traceable description xyz" in profile_body


def test_post_add_expense_no_description_redirects_and_saves_null(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.post("/expenses/add", data=valid_payload(description=""))
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")

    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT description FROM expenses WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (DEMO_USER_ID,),
        ).fetchone()
        conn.close()
    assert row["description"] is None


def test_post_add_expense_whitespace_only_description_stored_as_null(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    client.post("/expenses/add", data=valid_payload(description="   "))

    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT description FROM expenses WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (DEMO_USER_ID,),
        ).fetchone()
        conn.close()
    assert row["description"] is None


def test_post_add_expense_ignores_forged_user_id_field(client, app):
    """POST only carries amount/category/date/description per spec; the
    owning user must come from session['user_id'], not the request body."""
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    client.post(
        "/expenses/add",
        data=valid_payload(description="Forged owner check", user_id="999"),
    )

    with app.app_context():
        conn = get_db()
        forged = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = 999"
        ).fetchone()["c"]
        conn.close()
    assert forged == 0

    row = fetch_expense(app, DEMO_USER_ID, "Forged owner check")
    assert row is not None


# ------------------------------------------------------------------ #
# POST /expenses/add — validation errors                               #
# ------------------------------------------------------------------ #

def test_post_add_expense_missing_amount_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(amount=""))
    body = response.data.decode()
    assert response.status_code == 200
    assert has_alert(body)
    assert "<form" in body
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_zero_amount_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(amount="0"))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_negative_amount_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(amount="-5"))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_non_numeric_amount_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(amount="abc"))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_invalid_category_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post(
        "/expenses/add", data=valid_payload(category="Groceries")
    )
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_invalid_date_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post(
        "/expenses/add", data=valid_payload(date="not-a-date")
    )
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_missing_date_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(date=""))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_missing_category_rerenders_form_with_error(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(category=""))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


@pytest.mark.parametrize("amount", ["nan", "inf", "-inf", "10000000.01", "1e300"])
def test_post_add_expense_non_finite_or_huge_amount_rejected(client, app, amount):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post("/expenses/add", data=valid_payload(amount=amount))
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_amount_at_ceiling_accepted(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.post(
        "/expenses/add",
        data=valid_payload(amount="10000000", description="At the ceiling"),
    )
    assert response.status_code == 302
    row = fetch_expense(app, DEMO_USER_ID, "At the ceiling")
    assert row is not None
    assert row["amount"] == 10_000_000


def test_post_add_expense_description_over_200_chars_rejected(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before = count_expenses(app, DEMO_USER_ID)
    response = client.post(
        "/expenses/add", data=valid_payload(description="x" * 201)
    )
    assert response.status_code == 200
    assert has_alert(response.data.decode())
    assert count_expenses(app, DEMO_USER_ID) == before


def test_post_add_expense_description_exactly_200_chars_accepted(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    description = "x" * 200
    response = client.post(
        "/expenses/add", data=valid_payload(description=description)
    )
    assert response.status_code == 302
    assert fetch_expense(app, DEMO_USER_ID, description) is not None


# ------------------------------------------------------------------ #
# Stale session: logged-in user no longer exists                       #
# ------------------------------------------------------------------ #

def _login_then_delete_user(client, app):
    with app.app_context():
        user_id = create_user("Gone User", "gone@spendly.com", "password123")
    login(client, "gone@spendly.com", "password123")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    return user_id


@pytest.mark.parametrize("method", ["get", "post"])
def test_add_expense_stale_session_redirects_to_login(client, app, method):
    user_id = _login_then_delete_user(client, app)
    response = getattr(client, method)("/expenses/add", data=valid_payload())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert count_expenses(app, user_id) == 0
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ------------------------------------------------------------------ #
# Validation errors retain previously submitted values (spec: "re-      #
# populating previous values")                                         #
# ------------------------------------------------------------------ #

def test_post_add_expense_error_retains_amount_and_description(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    payload = valid_payload(amount="not-a-number", description="Keep this text")
    body = client.post("/expenses/add", data=payload).data.decode()
    assert "Keep this text" in body
    assert 'value="not-a-number"' in body


def test_post_add_expense_error_retains_selected_category(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    payload = valid_payload(amount="not-a-number", category="Transport")
    body = client.post("/expenses/add", data=payload).data.decode()
    # The previously chosen category option should be marked selected again.
    match = re.search(
        r'<option value="Transport"[^>]*>', body
    )
    assert match is not None
    assert "selected" in match.group(0)


def test_post_add_expense_error_retains_date(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    payload = valid_payload(amount="not-a-number", date="2026-05-15")
    body = client.post("/expenses/add", data=payload).data.decode()
    assert 'value="2026-05-15"' in body


# ------------------------------------------------------------------ #
# Definition of done: navigation                                       #
# ------------------------------------------------------------------ #

def test_navbar_shows_add_expense_link_when_logged_in(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/profile").data.decode()
    assert "Add Expense" in body
    assert 'href="/expenses/add"' in body


def test_navbar_hides_add_expense_link_when_logged_out(client):
    body = client.get("/").data.decode()
    assert 'href="/expenses/add"' not in body


def test_profile_page_has_add_expense_button_distinct_from_navbar(client):
    """DoD: 'The Add Expense button on the profile page navigates to
    /expenses/add' — the navbar link alone is not that button, so the
    profile page should link to /expenses/add more than once."""
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/profile").data.decode()
    assert body.count('href="/expenses/add"') >= 2


def test_currency_symbol_on_profile_is_rupee_not_dollar_or_pound(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    body = client.get("/profile").data.decode()
    assert "₹" in body
    assert "$" not in body
    assert "£" not in body
