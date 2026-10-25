"""Apply supabase/migrations/*.sql to the database in filename order.

    python supabase/migrate.py            # apply pending migrations
    python supabase/migrate.py --status   # list applied / pending, change nothing

Needs SUPABASE_DB_URL in .env (Supabase dashboard > Connect > Direct or Session pooler
connection string). Applied files are recorded in public.schema_migrations, so reruns
only run what is new. Each file is run once, inside its own transaction.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true", help="Show applied and pending migrations only")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("SUPABASE_DB_URL is not set in .env (Supabase dashboard > Connect > connection string).", file=sys.stderr)
        return 2

    import psycopg

    files = sorted(MIGRATIONS.glob("*.sql"))
    with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
            "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        conn.execute("ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY")
        conn.execute("REVOKE ALL ON TABLE public.schema_migrations FROM PUBLIC, anon, authenticated")
        done = {r[0] for r in conn.execute("SELECT name FROM public.schema_migrations")}
        pending = [f for f in files if f.name not in done]

        for f in files:
            print(f"  {'applied ' if f.name in done else 'pending '} {f.name}")
        if args.status:
            return 0
        if not pending:
            print("Nothing to apply.")
            return 0

        for f in pending:
            print(f"Applying {f.name} ...", end=" ", flush=True)
            try:
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO public.schema_migrations (name) VALUES (%s)", (f.name,))
            except Exception as exc:
                print("FAILED")
                print(f"  {type(exc).__name__}: {exc}", file=sys.stderr)
                return 1
            print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
