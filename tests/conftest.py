import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Point the app at a fresh, seeded SQLite file for each test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.init_db()
        db.seed_db()
    yield flask_app
