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
import tempfile
import time

import httpx

from .env import ROOT_ENV, load_env


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


def remember(address: str, env_file=ROOT_ENV) -> bool:
    """Write the address into .env as ENGANO_PUBLIC_URL (replacing the old one). True if the file changed.

    Only this one line is touched; the rest of the file, and its permissions, stay as they were.
    """
    try:
        text = env_file.read_text()
    except OSError:
        return False
    line = f"ENGANO_PUBLIC_URL={address}"
    if re.search(r"^ENGANO_PUBLIC_URL=.*$", text, re.M):
        new = re.sub(r"^ENGANO_PUBLIC_URL=.*$", lambda _: line, text, count=1, flags=re.M)
    else:
        new = text.rstrip("\n") + "\n\n# The backend's public address, written by `make start`; `make deploy` bakes it into the web app.\n" + line + "\n"
    if new == text:
        return False
    fd, tmp = tempfile.mkstemp(dir=env_file.parent, prefix=".env.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(new)
        os.chmod(tmp, env_file.stat().st_mode & 0o777)
        os.replace(tmp, env_file)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


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
    changed = remember(address)
    print(f"[api-url] Backend is public at  {address}" + ("  (saved to .env as ENGANO_PUBLIC_URL)" if changed else ""))
    print(f"[api-url] Share this link:       {site}/?api={address}")
    print("[api-url] or on the site's sign-in page: Server > Change > paste the address above.")
    origins = [o.strip().rstrip("/") for o in os.getenv("ENGANO_CORS_ORIGINS", "").split(",") if o.strip()]
    pattern = os.getenv("ENGANO_CORS_ORIGIN_REGEX", "")
    if site.startswith("https://") and "YOUR-SITE" not in site and site not in origins and not (pattern and re.fullmatch(pattern, site)):
        print(f"[api-url] Reminder: {site} is not allowed to call this backend yet. Add it to ENGANO_CORS_ORIGINS in .env and restart.")
    elif "YOUR-SITE" in site and not origins and not pattern:
        print("[api-url] Reminder: no hosted site is allowed yet. Set ENGANO_CORS_ORIGINS (or ENGANO_CORS_ORIGIN_REGEX) in .env and restart.")
    if changed and os.getenv("ENGANO_AUTO_DEPLOY", "").strip().lower() in ("1", "true", "yes"):
        # The address is new, so the published site is out of date: publish it again.
        from .deploy_site import main as deploy

        print("[api-url] ENGANO_AUTO_DEPLOY is on: publishing the web app with the new address")
        return deploy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
