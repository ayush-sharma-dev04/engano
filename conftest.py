import os
import tempfile

import pytest

# Set before anything is imported, so no test can fall back to the real app database
# (Backend/.data/engano.db) even if it clears the environment.
os.environ["ENGANO_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="engano-tests-"), "session.db")


@pytest.fixture(autouse=True)
def _app_database_in_tmp(tmp_path, monkeypatch):
    """create_app() opens the team database; give every test its own."""
    monkeypatch.setenv("ENGANO_DB_PATH", str(tmp_path / "app.db"))


@pytest.fixture(autouse=True)
def _open_endpoints_for_tests(monkeypatch):
    """Most tests call /api/review without signing in; the login requirement has its own tests."""
    monkeypatch.setenv("ENGANO_REQUIRE_LOGIN", "0")


@pytest.fixture(autouse=True)
def _never_touch_the_real_supabase(monkeypatch):
    """Test accounts must never be mirrored into the developer's real Supabase Auth."""
    for name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL"):
        monkeypatch.delenv(name, raising=False)
