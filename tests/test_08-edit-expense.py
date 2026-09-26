"""
Tests for Step 8 — Edit Expense (spec: .claude/specs/08-edit-expense.md).

Derived from the spec's routes, access rules, query-helper contracts,
templates section and Definition of done list — not from reading app.py's
implementation logic.
"""

import re

import pytest

from database.db import create_user, get_db
from database.queries import get_expense_by_id, update_expense

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_USER_ID = 1

SECOND_EMAIL = "second@spendly.com"
SECOND_PASSWORD = "password123"


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def valid_payload(**overrides):
    payload = {
        "amount": "75.50",
        "category": "Transport",
        "date": "2026-04-10",
        "description": "Updated description",
    }
    payload.update(overrides)
    return payload


def has_alert(html):
    """A structural signal that an error message was rendered, without
    pinning the test to exact wording (spec does not fix error text)."""
    return 'role="alert"' in html


def get_expense_row(app, expense_id):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


def first_expense_id(app, user_id=DEMO_USER_ID):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM expenses WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return row["id"]


def missing_expense_id(app):
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT MAX(id) AS m FROM expenses").fetchone()
        conn.close()
        return (row["m"] or 0) + 1000


# ------------------------------------------------------------------ #
# Unit tests: get_expense_by_id / update_expense                      #
# ------------------------------------------------------------------ #

def test_get_expense_by_id_returns_dict_for_owner(app):
    expense_id = first_expense_id(app)
    with app.app_context():
        expense = get_expense_by_id(expense_id, DEMO_USER_ID)

    assert expense is not None
    assert expense["id"] == expense_id
    assert {"id", "amount", "category", "date", "description"} <= set(
        expense.keys()
    )


def test_get_expense_by_id_returns_none_for_wrong_user(app):
    expense_id = first_expense_id(app)
    with app.app_context():
        expense = get_expense_by_id(expense_id, 999)

    assert expense is None


def test_get_expense_by_id_returns_none_for_missing_id(app):
    missing_id = missing_expense_id(app)
    with app.app_context():
        expense = get_expense_by_id(missing_id, DEMO_USER_ID)

    assert expense is None


def test_update_expense_returns_true_and_changes_row(app):
    expense_id = first_expense_id(app)
    with app.app_context():
        result = update_expense(
            expense_id,
            DEMO_USER_ID,
            amount=99.99,
            category="Health",
            date="2026-01-15",
            description="Changed",
        )

    row = get_expense_row(app, expense_id)
    assert result is True
    assert row["amount"] == 99.99
    assert row["category"] == "Health"
    assert row["date"] == "2026-01-15"
    assert row["description"] == "Changed"


def test_update_expense_returns_false_for_wrong_user_and_row_unchanged(app):
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    with app.app_context():
        result = update_expense(
            expense_id,
            999,
            amount=1.23,
            category="Other",
            date="2026-02-02",
            description="Should not apply",
        )

    after = get_expense_row(app, expense_id)
    assert result is False
    assert after == before


def test_update_expense_stores_none_description_as_null(app):
    expense_id = first_expense_id(app)
    with app.app_context():
        update_expense(
            expense_id,
            DEMO_USER_ID,
            amount=10.0,
            category="Food",
            date="2026-03-03",
            description=None,
        )

    row = get_expense_row(app, expense_id)
    assert row["description"] is None


def test_update_expense_leaves_user_id_and_created_at_unchanged(app):
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    with app.app_context():
        update_expense(
            expense_id,
            DEMO_USER_ID,
            amount=55.55,
            category="Bills",
            date="2026-04-04",
            description="Anything",
        )

    after = get_expense_row(app, expense_id)
    assert after["user_id"] == before["user_id"]
    assert after["created_at"] == before["created_at"]


# ------------------------------------------------------------------ #
# Access: logged out, stale session, missing/foreign id -> 404         #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("method", ["get", "post"])
def test_edit_expense_unauthenticated_redirects_to_login(client, app, method):
    expense_id = first_expense_id(app)
    response = getattr(client, method)(
        f"/expenses/{expense_id}/edit", data=valid_payload()
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


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
def test_edit_expense_stale_session_redirects_to_login_and_clears_session(
    client, app, method
):
    _login_then_delete_user(client, app)
    expense_id = first_expense_id(app)

    response = getattr(client, method)(
        f"/expenses/{expense_id}/edit", data=valid_payload()
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


@pytest.mark.parametrize("method", ["get", "post"])
def test_edit_expense_missing_id_returns_404(client, app, method):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    missing_id = missing_expense_id(app)

    response = getattr(client, method)(
        f"/expenses/{missing_id}/edit", data=valid_payload()
    )
    assert response.status_code == 404


def test_get_edit_expense_another_users_expense_returns_404(client, app):
    with app.app_context():
        create_user("Other User", SECOND_EMAIL, SECOND_PASSWORD)
    login(client, SECOND_EMAIL, SECOND_PASSWORD)
    demo_expense_id = first_expense_id(app)

    response = client.get(f"/expenses/{demo_expense_id}/edit")
    assert response.status_code == 404


def test_post_edit_expense_another_users_expense_returns_404_and_owner_row_unchanged(
    client, app
):
    with app.app_context():
        create_user("Other User", SECOND_EMAIL, SECOND_PASSWORD)
    login(client, SECOND_EMAIL, SECOND_PASSWORD)
    demo_expense_id = first_expense_id(app)
    before = get_expense_row(app, demo_expense_id)

    response = client.post(
        f"/expenses/{demo_expense_id}/edit",
        data=valid_payload(description="Hacked by second user"),
    )

    assert response.status_code == 404
    assert get_expense_row(app, demo_expense_id) == before


# ------------------------------------------------------------------ #
# GET /expenses/<id>/edit — owner                                     #
# ------------------------------------------------------------------ #

def test_get_edit_expense_as_owner_returns_200(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    response = client.get(f"/expenses/{expense_id}/edit")
    assert response.status_code == 200


def test_get_edit_expense_form_action_points_to_edit_url(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get(f"/expenses/{expense_id}/edit").data.decode()
    assert f'action="/expenses/{expense_id}/edit"' in body


def test_get_edit_expense_prefills_current_values(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    row = get_expense_row(app, expense_id)

    body = client.get(f"/expenses/{expense_id}/edit").data.decode()

    expected_amount = f"{row['amount']:.2f}"
    assert f'value="{expected_amount}"' in body

    match = re.search(rf'<option value="{row["category"]}"[^>]*>', body)
    assert match is not None
    assert "selected" in match.group(0)

    assert f'value="{row["date"]}"' in body
    if row["description"]:
        assert f'value="{row["description"]}"' in body


def test_get_edit_expense_has_cancel_link_back_to_profile(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get(f"/expenses/{expense_id}/edit").data.decode()
    assert 'href="/profile"' in body


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — happy path                               #
# ------------------------------------------------------------------ #

def test_post_edit_expense_valid_data_redirects_and_updates_row(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    response = client.post(
        f"/expenses/{expense_id}/edit",
        data=valid_payload(
            amount="123.45",
            category="Health",
            date="2026-05-05",
            description="Edited entry",
        ),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")

    row = get_expense_row(app, expense_id)
    assert row["amount"] == 123.45
    assert row["category"] == "Health"
    assert row["date"] == "2026-05-05"
    assert row["description"] == "Edited entry"


def test_post_edit_expense_empty_description_stores_null(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(description="")
    )

    assert response.status_code == 302
    row = get_expense_row(app, expense_id)
    assert row["description"] is None


def test_post_edit_expense_updates_reflected_on_profile_page(client, app):
    """DoD: saving redirects to /profile, and the row shows the new values."""
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    client.post(
        f"/expenses/{expense_id}/edit",
        data=valid_payload(description="Traceable edited marker"),
    )

    body = client.get("/profile").data.decode()
    assert "Traceable edited marker" in body


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — validation errors                        #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("amount", ["", "0", "-5", "abc"])
def test_post_edit_expense_invalid_amount_rerenders_with_error_and_leaves_row(
    client, app, amount
):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    response = client.post(
        f"/expenses/{expense_id}/edit",
        data=valid_payload(amount=amount, description="Kept description"),
    )
    body = response.data.decode()

    assert response.status_code == 200
    assert has_alert(body)
    assert f'value="{amount}"' in body
    assert "Kept description" in body
    assert get_expense_row(app, expense_id) == before


def test_post_edit_expense_invalid_category_rerenders_with_error_and_leaves_row(
    client, app
):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(category="Groceries")
    )
    body = response.data.decode()

    assert response.status_code == 200
    assert has_alert(body)
    assert get_expense_row(app, expense_id) == before


def test_post_edit_expense_invalid_date_rerenders_with_error_and_leaves_row(
    client, app
):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(date="not-a-date")
    )
    body = response.data.decode()

    assert response.status_code == 200
    assert has_alert(body)
    assert 'value="not-a-date"' in body
    assert get_expense_row(app, expense_id) == before


# ------------------------------------------------------------------ #
# Profile page: Edit link per row                                     #
# ------------------------------------------------------------------ #

def test_profile_page_has_edit_link_for_each_expense(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    with app.app_context():
        conn = get_db()
        ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM expenses WHERE user_id = ?", (DEMO_USER_ID,)
            ).fetchall()
        ]
        conn.close()

    body = client.get("/profile").data.decode()
    for expense_id in ids:
        assert f'href="/expenses/{expense_id}/edit"' in body
