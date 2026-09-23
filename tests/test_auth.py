DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
INVALID_MSG = b"Invalid email or password."
REQUIRED_MSG = b"Email and password are required."


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def test_login_page_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'action="/login"' in response.data
    assert b"Sign in" in response.data


def test_login_with_demo_user_sets_session(client):
    response = login(client, DEMO_EMAIL, DEMO_PASSWORD)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    with client.session_transaction() as sess:
        assert sess["user_id"] == 1


def test_login_email_is_case_insensitive_and_trimmed(client):
    response = login(client, "  DEMO@Spendly.com ", DEMO_PASSWORD)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_wrong_password_shows_generic_error(client):
    response = login(client, DEMO_EMAIL, "wrong-password")
    assert response.status_code == 200
    assert INVALID_MSG in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_unknown_email_shows_same_error(client):
    response = login(client, "nobody@spendly.com", DEMO_PASSWORD)
    assert response.status_code == 200
    assert INVALID_MSG in response.data


def test_empty_fields_show_required_error(client):
    assert REQUIRED_MSG in login(client, "", DEMO_PASSWORD).data
    assert REQUIRED_MSG in login(client, DEMO_EMAIL, "").data


def test_email_is_kept_after_failed_login(client):
    response = login(client, DEMO_EMAIL, "wrong-password")
    assert f'value="{DEMO_EMAIL}"'.encode() in response.data


def test_registered_user_can_log_back_in(client):
    client.post(
        "/register",
        data={"name": "Asha", "email": "asha@example.com", "password": "secret123"},
    )
    client.get("/logout")
    response = login(client, "asha@example.com", "secret123")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_login_page_redirects_when_logged_in(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_logout_clears_session_and_redirects(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_when_logged_out_redirects(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_navbar_reflects_session(client):
    landing = client.get("/").data
    assert b"Sign in" in landing
    assert b"Sign out" not in landing

    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    landing = client.get("/", follow_redirects=True).data
    assert b"Sign out" in landing
    assert b"Demo User" in landing
    assert b"Get started" not in landing

    client.get("/logout")
    landing = client.get("/").data
    assert b"Sign in" in landing
    assert b"Sign out" not in landing


def test_login_sets_user_name_in_session(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    with client.session_transaction() as sess:
        assert sess["user_name"] == "Demo User"


def test_register_sets_user_name_in_session(client):
    client.post(
        "/register",
        data={"name": "Asha", "email": "asha@example.com", "password": "secret123"},
    )
    with client.session_transaction() as sess:
        assert sess["user_name"] == "Asha"


def test_logout_clears_user_name(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "user_name" not in sess


def test_landing_redirects_to_profile_when_logged_in(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_register_page_redirects_when_logged_in(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/register")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_landing_renders_when_logged_out(client):
    assert client.get("/").status_code == 200
