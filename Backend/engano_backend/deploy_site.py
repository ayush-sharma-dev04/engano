"""Build the web app with the backend address from .env and publish it to Netlify.

    make deploy

The address is VITE_API_URL in .env. If that is empty, the address of the running tunnel is used (so it
also works with a quick tunnel whose address changes: start `make start`, then `make deploy`).
Needs NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID in .env (Netlify > User settings > Applications > personal
access token; Site configuration > Site ID). Nothing but VITE_ variables ever reaches the built site.
"""

import os
import subprocess
import sys
from pathlib import Path

from .env import REPO_ROOT, load_env
from .public_url import answers, tunnel_address

FRONTEND = REPO_ROOT / "Frontend"


def choose_api_url(configured: str | None, tunnel: str | None, remembered: str | None = None) -> str | None:
    """The address to bake in, first that applies: VITE_API_URL in .env, the running tunnel, the last one `make start`
    saved (ENGANO_PUBLIC_URL). https only (a hosted page can't call http)."""
    for candidate in ((configured or "").strip().rstrip("/"), tunnel or "", (remembered or "").strip().rstrip("/")):
        if candidate.startswith("https://"):
            return candidate
    return None


def main() -> int:
    load_env()
    missing = [k for k in ("NETLIFY_AUTH_TOKEN", "NETLIFY_SITE_ID") if not os.getenv(k, "").strip()]
    if missing:
        print(f"[deploy] Add {' and '.join(missing)} to .env first (see docs/hosting.md).")
        return 1

    configured = os.getenv("VITE_API_URL")
    tunnel = tunnel_address(os.getenv("TUNNEL_METRICS", "127.0.0.1:20249")) if not (configured or "").strip() else None
    api = choose_api_url(configured, tunnel, os.getenv("ENGANO_PUBLIC_URL"))
    if not api:
        print("[deploy] No https backend address. Set VITE_API_URL in .env, or start the tunnel first (`make start`).")
        return 1
    if not answers(api):
        print(f"[deploy] Warning: {api} does not answer right now. Publishing anyway; start the backend before using the site.")
    print(f"[deploy] Building the web app for the backend at {api}")

    env = {**os.environ, "VITE_API_URL": api}
    if not (FRONTEND / "node_modules").exists():
        subprocess.run(["npm", "--prefix", str(FRONTEND), "ci"], check=True, env=env)
    subprocess.run(["npm", "--prefix", str(FRONTEND), "run", "build"], check=True, env=env)

    print("[deploy] Publishing to Netlify")
    result = subprocess.run(
        ["npx", "--yes", "netlify-cli", "deploy", "--prod", "--dir", str(FRONTEND / "dist"), "--site", os.environ["NETLIFY_SITE_ID"]],
        env=env,  # NETLIFY_AUTH_TOKEN travels in the environment, not on the command line
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
