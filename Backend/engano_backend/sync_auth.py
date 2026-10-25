"""Backfill: list every existing ENGANO account under Supabase Authentication → Users.

    python -m engano_backend.sync_auth

Safe to run again. People who signed up before the secret key was set get a random Supabase
password (they keep signing in to ENGANO with the password they chose).
"""

import os
from pathlib import Path

from .auth_mirror import AuthMirror
from .env import load_env
from .team_store import TeamStore


def main() -> int:
    load_env()
    mirror = AuthMirror.from_env()
    if not mirror.enabled:
        print("Set SUPABASE_SECRET_KEY (or SUPABASE_DB_URL) in .env first.")
        return 1
    store = TeamStore(os.getenv("ENGANO_DB_PATH") or Path(__file__).resolve().parent.parent / ".data" / "engano.db")
    done = skipped = 0
    for account in store.accounts_to_mirror():
        supabase_id = mirror.push(account)
        if supabase_id:
            store.set_supabase_id(account["id"], supabase_id)
            done += 1
        else:
            skipped += 1
    print(f"Added {done} account(s) to Supabase Auth; {skipped} skipped (already there or refused: see log).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
