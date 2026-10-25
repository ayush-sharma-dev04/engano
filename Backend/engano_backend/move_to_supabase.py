"""Copy the app's data from the local SQLite file into Supabase.

    make migrate        # once: creates the tables
    make move-data      # copies accounts, workspaces, drafts, history... (safe to run again)

Rows keep their ids, so sign-ins, join codes and links stay valid. Rows already in Supabase are left
alone. The SQLite file is not touched or deleted: keep it as a backup.
"""

import os
import sqlite3
import sys
from pathlib import Path

from .env import load_env

# Parents before children.
TABLES = [
    ("meta", "key"),
    ("accounts", "id"),
    ("sessions", "token_hash"),
    ("workspaces", "id"),
    ("members", "id"),
    ("requests", "id"),
    ("assignments", "id"),
    ("guidelines", "id"),
    ("submissions", "id"),
    ("reviewer_actions", "id"),
    ("submission_versions", "id"),
    ("submission_events", "id"),
]
IDENTITY = {"workspaces", "members", "requests", "assignments", "guidelines", "submissions", "reviewer_actions", "submission_versions", "submission_events"}


def main() -> int:
    load_env()
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    source = Path(os.getenv("ENGANO_SOURCE_DB") or Path(__file__).resolve().parent.parent / ".data" / "engano.db")
    if not url:
        print("Set SUPABASE_DB_URL in .env first.")
        return 1
    if not source.exists():
        print(f"No local data to move ({source} does not exist).")
        return 0

    import psycopg

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    have = {r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    with psycopg.connect(url, connect_timeout=20) as dst:
        if not dst.execute("SELECT to_regclass('submission_events')").fetchone()[0]:
            print("The tables are missing in Supabase. Run `make migrate` first.")
            return 1
        for table, key in TABLES:
            if table not in have:
                continue
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"  {table}: nothing to copy")
                continue
            cols = rows[0].keys()
            if table == "sessions":
                import time

                rows = [r for r in rows if r["expires_at"] > time.time()]
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) ON CONFLICT ({key}) DO NOTHING"
            with dst.cursor() as cur:
                cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
                copied = cur.rowcount
            print(f"  {table}: {len(rows)} in the file, {copied if copied >= 0 else len(rows)} copied")
            if table in IDENTITY:
                dst.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), (SELECT COUNT(*) FROM {table}) > 0)"
                )
        dst.commit()
    print("Done. Start the backend without ENGANO_DB_PATH and it uses Supabase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
