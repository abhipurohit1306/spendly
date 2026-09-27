DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def test_analytics_redirects_logged_out_user_to_login(client):
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_analytics_renders_for_logged_in_user(client):
    login(client)
    response = client.get("/analytics")
    assert response.status_code == 200
    assert b"Coming soon" in response.data


def test_navbar_hides_analytics_when_logged_out(client):
    response = client.get("/login")
    assert b'href="/analytics"' not in response.data


def test_navbar_shows_analytics_when_logged_in(client):
    login(client)
    response = client.get("/profile")
    assert b'href="/analytics"' in response.data


def test_navbar_marks_analytics_active_on_analytics_page(client):
    login(client)
    html = client.get("/analytics").get_data(as_text=True)
    assert '<a href="/analytics" class="nav-link--active" aria-current="page">Analytics</a>' in html
    assert '<a href="/profile">Profile</a>' in html


def test_navbar_marks_profile_active_on_profile_page(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert '<a href="/profile" class="nav-link--active" aria-current="page">Profile</a>' in html
    assert '<a href="/analytics">Analytics</a>' in html
