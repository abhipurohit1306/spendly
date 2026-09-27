"""
Tests for Step 9 — Delete Expense (spec: .claude/specs/09-delete-expense.md).

Derived from the spec's routes, access rules, query-helper contract,
templates section and Definition of done list — not from reading app.py's
implementation logic.
"""

import pytest

from database.db import create_user, get_db
from database.queries import delete_expense, get_expense_by_id, get_summary_stats

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_USER_ID = 1

SECOND_EMAIL = "second@spendly.com"
SECOND_PASSWORD = "password123"


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def get_expense_row(app, expense_id):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


def all_expense_rows(app, user_id=DEMO_USER_ID):
    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
        conn.close()
        return {row["id"]: dict(row) for row in rows}


def expense_id_for_category(app, category, user_id=DEMO_USER_ID):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM expenses WHERE user_id = ? AND category = ? "
            "ORDER BY id LIMIT 1",
            (user_id, category),
        ).fetchone()
        conn.close()
        return row["id"]


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


def render_date(app, raw_date):
    """Render raw_date through the app's own date_fmt filter, so the
    expected text is produced by the feature itself, not re-derived."""
    with app.app_context():
        return app.jinja_env.filters["date_fmt"](raw_date)


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


# ------------------------------------------------------------------ #
# Unit tests: delete_expense query helper                             #
# ------------------------------------------------------------------ #

def test_delete_expense_returns_true_and_removes_row(app):
    expense_id = first_expense_id(app)
    with app.app_context():
        result = delete_expense(expense_id, DEMO_USER_ID)

    assert result is True
    assert get_expense_row(app, expense_id) is None


def test_delete_expense_returns_false_for_wrong_user_and_row_survives(app):
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    with app.app_context():
        result = delete_expense(expense_id, 999)

    assert result is False
    assert get_expense_row(app, expense_id) == before


def test_delete_expense_returns_false_for_missing_id(app):
    missing_id = missing_expense_id(app)
    with app.app_context():
        result = delete_expense(missing_id, DEMO_USER_ID)

    assert result is False


def test_get_expense_by_id_still_used_for_confirmation_lookup(app):
    """Sanity check that the existing helper is reusable for the
    confirmation page and ownership check (spec depends on Step 8)."""
    expense_id = first_expense_id(app)
    with app.app_context():
        expense = get_expense_by_id(expense_id, DEMO_USER_ID)
    assert expense is not None
    assert expense["id"] == expense_id


# ------------------------------------------------------------------ #
# Access: logged out, stale session, missing/foreign id -> 404         #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("method", ["get", "post"])
def test_delete_expense_unauthenticated_redirects_to_login_and_deletes_nothing(
    client, app, method
):
    expense_id = first_expense_id(app)

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert get_expense_row(app, expense_id) is not None


@pytest.mark.parametrize("method", ["get", "post"])
def test_delete_expense_stale_session_redirects_to_login_and_clears_session(
    client, app, method
):
    _login_then_delete_user(client, app)
    expense_id = first_expense_id(app)

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


@pytest.mark.parametrize("method", ["get", "post"])
def test_delete_expense_missing_id_returns_404(client, app, method):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    missing_id = missing_expense_id(app)

    response = getattr(client, method)(f"/expenses/{missing_id}/delete")
    assert response.status_code == 404


def test_get_delete_expense_another_users_expense_returns_404(client, app):
    with app.app_context():
        create_user("Other User", SECOND_EMAIL, SECOND_PASSWORD)
    login(client, SECOND_EMAIL, SECOND_PASSWORD)
    demo_expense_id = first_expense_id(app)

    response = client.get(f"/expenses/{demo_expense_id}/delete")
    assert response.status_code == 404


def test_post_delete_expense_another_users_expense_returns_404_and_row_survives(
    client, app
):
    with app.app_context():
        create_user("Other User", SECOND_EMAIL, SECOND_PASSWORD)
    login(client, SECOND_EMAIL, SECOND_PASSWORD)
    demo_expense_id = first_expense_id(app)
    before = get_expense_row(app, demo_expense_id)

    response = client.post(f"/expenses/{demo_expense_id}/delete")

    assert response.status_code == 404
    assert get_expense_row(app, demo_expense_id) == before


# ------------------------------------------------------------------ #
# GET /expenses/<id>/delete — confirmation page                       #
# ------------------------------------------------------------------ #

def test_get_delete_expense_as_owner_returns_200(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    response = client.get(f"/expenses/{expense_id}/delete")
    assert response.status_code == 200


def test_get_delete_expense_shows_expense_summary(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    row = get_expense_row(app, expense_id)

    body = client.get(f"/expenses/{expense_id}/delete").data.decode()

    assert render_date(app, row["date"]) in body
    assert row["category"] in body
    assert f"₹{row['amount']:.2f}" in body
    assert row["description"] in body


def test_get_delete_expense_shows_em_dash_for_null_description(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "UPDATE expenses SET description = NULL WHERE id = ?", (expense_id,)
        )
        conn.commit()
        conn.close()

    body = client.get(f"/expenses/{expense_id}/delete").data.decode()
    assert "—" in body


def test_get_delete_expense_has_cancel_link_to_profile(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get(f"/expenses/{expense_id}/delete").data.decode()
    assert 'href="/profile"' in body


def test_get_delete_expense_form_posts_to_delete_url(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get(f"/expenses/{expense_id}/delete").data.decode()
    assert f'action="/expenses/{expense_id}/delete"' in body
    assert 'method="POST"' in body


def test_get_delete_expense_does_not_delete_and_profile_still_shows_it(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    before = get_expense_row(app, expense_id)

    client.get(f"/expenses/{expense_id}/delete")

    assert get_expense_row(app, expense_id) == before

    profile_body = client.get("/profile").data.decode()
    assert f"/expenses/{expense_id}/edit" in profile_body


# ------------------------------------------------------------------ #
# POST /expenses/<id>/delete — happy path and side effects             #
# ------------------------------------------------------------------ #

def test_post_delete_expense_redirects_to_profile(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_post_delete_expense_removes_row_and_leaves_others_untouched(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    before_all = all_expense_rows(app)
    expense_id = first_expense_id(app)

    client.post(f"/expenses/{expense_id}/delete")

    assert get_expense_row(app, expense_id) is None
    after_all = all_expense_rows(app)
    assert expense_id not in after_all
    del before_all[expense_id]
    assert after_all == before_all


def test_post_delete_expense_updates_profile_count_and_total(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)
    deleted_amount = get_expense_row(app, expense_id)["amount"]

    with app.app_context():
        before_stats = get_summary_stats(DEMO_USER_ID)

    client.post(f"/expenses/{expense_id}/delete")

    with app.app_context():
        after_stats = get_summary_stats(DEMO_USER_ID)

    assert after_stats["transaction_count"] == before_stats["transaction_count"] - 1
    assert after_stats["total_spent"] == round(
        before_stats["total_spent"] - deleted_amount, 2
    )

    after_body = client.get("/profile").data.decode()
    assert f"₹{after_stats['total_spent']:.2f}" in after_body
    assert f">{after_stats['transaction_count']}<" in after_body
    # The deleted row's own edit/delete links are gone from the table.
    assert f"/expenses/{expense_id}/edit" not in after_body
    assert f"/expenses/{expense_id}/delete" not in after_body


def test_post_delete_expense_last_in_category_removes_it_from_breakdown(
    client, app
):
    """DoD: deleting a user's only expense in a category removes that
    category from the breakdown. The seeded demo data has exactly one
    'Health' expense."""
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    health_id = expense_id_for_category(app, "Health")

    before_body = client.get("/profile").data.decode()
    assert "profile-badge--health" in before_body

    client.post(f"/expenses/{health_id}/delete")

    after_body = client.get("/profile").data.decode()
    assert "profile-badge--health" not in after_body


def test_post_delete_expense_then_repeat_post_returns_404(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    first_response = client.post(f"/expenses/{expense_id}/delete")
    assert first_response.status_code == 302

    second_response = client.post(f"/expenses/{expense_id}/delete")
    assert second_response.status_code == 404


# ------------------------------------------------------------------ #
# Profile page: Delete link per row                                    #
# ------------------------------------------------------------------ #

def test_profile_page_has_delete_link_with_aria_label_for_each_expense(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT id, date FROM expenses WHERE user_id = ?", (DEMO_USER_ID,)
        ).fetchall()
        conn.close()

    body = client.get("/profile").data.decode()
    for row in rows:
        assert f'href="/expenses/{row["id"]}/delete"' in body
        expected_label = f'aria-label="Delete expense from {render_date(app, row["date"])}"'
        assert expected_label in body


def test_profile_page_row_has_both_edit_and_delete_links(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get("/profile").data.decode()
    assert f'href="/expenses/{expense_id}/edit"' in body
    assert f'href="/expenses/{expense_id}/delete"' in body


# ------------------------------------------------------------------ #
# Edit page: "Delete this expense" link                                #
# ------------------------------------------------------------------ #

def test_edit_expense_page_has_delete_link_to_confirmation_page(client, app):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    expense_id = first_expense_id(app)

    body = client.get(f"/expenses/{expense_id}/edit").data.decode()
    assert f'href="/expenses/{expense_id}/delete"' in body
