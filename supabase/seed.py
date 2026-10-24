"""Load brand policies from data/brand_library/*.json into public.brand_policies.

    python supabase/seed.py              # show what would change
    python supabase/seed.py --apply      # write it

Needs SUPABASE_DB_URL in .env. Idempotent: unchanged brands are left alone, changed
brands are updated and their `version` is bumped. The policy is validated with the
engine's own BrandPolicy model first, so a malformed file never reaches the database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai_engine.schemas.brand_policy import BrandPolicy  # noqa: E402

LIBRARY = ROOT / "data" / "brand_library"
JSON_COLUMNS = (
    "approved_terminology", "claims_policy", "factual_rules", "offers",
    "tone_rules", "accessibility_rules", "legal_rules",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Write to the database (default: dry run)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("SUPABASE_DB_URL is not set in .env.", file=sys.stderr)
        return 2

    import psycopg
    from psycopg.types.json import Jsonb

    policies = []
    for path in sorted(LIBRARY.glob("*.json")):
        policy = BrandPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))
        policies.append((path.name, policy))

    with psycopg.connect(url, connect_timeout=15) as conn:
        for name, p in policies:
            data = json.loads(p.model_dump_json())  # JSON-safe (dates as strings)
            row = conn.execute(
                "SELECT brand_name, description, " + ", ".join(JSON_COLUMNS) + ", version "
                "FROM public.brand_policies WHERE brand_id = %s",
                (p.brand_id,),
            ).fetchone()
            wanted = [data["brand_name"], data["description"]] + [data[c] for c in JSON_COLUMNS]
            if row is None:
                action = "insert"
            elif list(row[:-1]) == wanted:
                print(f"  unchanged {p.brand_id:14} (v{row[-1]}) <- {name}")
                continue
            else:
                action = "update"
            print(f"  {action:9} {p.brand_id:14} <- {name}")
            if not args.apply:
                continue
            if action == "insert":
                conn.execute(
                    "INSERT INTO public.brand_policies (brand_id, brand_name, description, "
                    + ", ".join(JSON_COLUMNS) + ") VALUES (%s, %s, %s, " + ", ".join(["%s"] * len(JSON_COLUMNS)) + ")",
                    [p.brand_id, data["brand_name"], data["description"]] + [Jsonb(data[c]) for c in JSON_COLUMNS],
                )
            else:
                conn.execute(
                    "UPDATE public.brand_policies SET brand_name = %s, description = %s, "
                    + ", ".join(f"{c} = %s" for c in JSON_COLUMNS)
                    + ", version = version + 1, updated_at = NOW() WHERE brand_id = %s",
                    [data["brand_name"], data["description"]] + [Jsonb(data[c]) for c in JSON_COLUMNS] + [p.brand_id],
                )
        if args.apply:
            conn.commit()
            print("Done.")
        else:
            print("Dry run only. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
