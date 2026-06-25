import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    import database.db as db_module

    # Redirect all DB operations to an isolated temp database before any query runs.
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))

    # Import app after patching so the module-level init_db()/seed_db() calls
    # (inside `with app.app_context()`) hit the temp DB on first import.
    # On subsequent tests the module is cached, so we re-run them explicitly below.
    import app as app_module

    flask_app = app_module.app
    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")

    with flask_app.app_context():
        db_module.init_db()
        db_module.seed_db()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_user_id(app):
    """Return the user_id of the seeded demo@spendly.com account."""
    import database.db as db_module

    conn = db_module.get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]
