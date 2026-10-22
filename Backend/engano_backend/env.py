from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
# The shared .env lives at the repo root (engano/.env).
ROOT_ENV = REPO_ROOT / ".env"


def load_env() -> None:
    """Load the root .env into os.environ (ai_engine's EngineConfig reads it from there)."""
    load_dotenv(ROOT_ENV)
