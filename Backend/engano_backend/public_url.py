"""Show the backend's public address and how to point the hosted web app at it.

    make api-url          # print it once (the tunnel must be running: `make start` or `make tunnel`)
    python -m engano_backend.public_url --wait   # wait for the tunnel (used by `make start`)

A quick Cloudflare tunnel gets a new address every time it starts, so the hosted site can be told the
new one from its sign-in page (Server > Change) or with a link that carries ?api=.
"""

import argparse
import os
import re
import sys
import time

import httpx

from .env import load_env


def tunnel_address(metrics: str) -> str | None:
    try:
        host = httpx.get(f"http://{metrics}/quicktunnel", timeout=2).json().get("hostname")
    except (httpx.HTTPError, ValueError):
        return None
    return f"https://{host}" if host else None


def answers(address: str) -> bool:
    try:
        return httpx.get(f"{address}/api/health", timeout=6).status_code == 200
    except httpx.HTTPError:
        return False


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="127.0.0.1:20249", help="cloudflared metrics address")
    parser.add_argument("--wait", action="store_true", help="wait for the tunnel to come up")
    args = parser.parse_args()

    deadline = time.monotonic() + (90 if args.wait else 0)
    address = tunnel_address(args.metrics)
    while not (address and answers(address)) and time.monotonic() < deadline:
        time.sleep(2)
        address = tunnel_address(args.metrics)
    if not address:
        print("[api-url] No tunnel is running. Start one with `make start` (or `make tunnel`).")
        return 1
    if not answers(address):
        print(f"[api-url] The tunnel is up at {address} but the backend does not answer through it yet. Is `make backend` running?")
        return 1

    site = (os.getenv("ENGANO_STUDIO_URL") or "https://YOUR-SITE.netlify.app").rstrip("/")
    print(f"[api-url] Backend is public at  {address}")
    print(f"[api-url] Share this link:       {site}/?api={address}")
    print("[api-url] or on the site's sign-in page: Server > Change > paste the address above.")
    origins = [o.strip().rstrip("/") for o in os.getenv("ENGANO_CORS_ORIGINS", "").split(",") if o.strip()]
    pattern = os.getenv("ENGANO_CORS_ORIGIN_REGEX", "")
    if site.startswith("https://") and "YOUR-SITE" not in site and site not in origins and not (pattern and re.fullmatch(pattern, site)):
        print(f"[api-url] Reminder: {site} is not allowed to call this backend yet. Add it to ENGANO_CORS_ORIGINS in .env and restart.")
    elif "YOUR-SITE" in site and not origins and not pattern:
        print("[api-url] Reminder: no hosted site is allowed yet. Set ENGANO_CORS_ORIGINS (or ENGANO_CORS_ORIGIN_REGEX) in .env and restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
