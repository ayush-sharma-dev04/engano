import pytest


@pytest.fixture(autouse=True)
def _no_real_reviewer(monkeypatch):
    """Tests must never pick up the developer's real reviewer from .env."""
    for name in ("ENGANO_REVIEWER_WHATSAPP", "ENGANO_REVIEWER_DISCORD_ID"):
        monkeypatch.delenv(name, raising=False)
