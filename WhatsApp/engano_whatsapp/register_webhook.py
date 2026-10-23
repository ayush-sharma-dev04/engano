"""Point Meta's WhatsApp webhook at the current public URL.

Usage (from the repo root; also `python -m engano_whatsapp.register_webhook`):
    make webhook                      # use the running `make tunnel` quick tunnel
    make webhook URL=https://my.host  # or a given base URL
    make start                        # runs this with --wait after starting the tunnel

Quick tunnels get a new URL every time cloudflared starts, so this runs after
each tunnel start. Needs WHATSAPP_APP_ID, WHATSAPP_BUSINESS_ACCOUNT_ID,
WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN and WHATSAPP_ACCESS_TOKEN in .env.
"""

import argparse
import os
import sys
import time

import httpx

from engano_backend.env import ROOT_ENV, load_env

WEBHOOK_PATH = "/api/webhooks/whatsapp"
REQUIRED = (
    "WHATSAPP_APP_ID",
    "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "WHATSAPP_APP_SECRET",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_ACCESS_TOKEN",
)


def say(message: str) -> None:
    print(f"[webhook] {message}", flush=True)


def wait_for(description: str, check, timeout: float, interval: float = 2.0):
    """Call check() until it returns something truthy, or give up after timeout."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = check()
        except (httpx.HTTPError, ValueError):
            result = None
        if result:
            return result
        if time.monotonic() > deadline:
            sys.exit(f"[webhook] Gave up waiting for {description}.")
        time.sleep(interval)


def tunnel_hostname(metrics: str) -> str | None:
    # cloudflared reports the quick tunnel hostname on its metrics server.
    resp = httpx.get(f"http://{metrics}/quicktunnel", timeout=2)
    hostname = resp.json().get("hostname")
    return f"https://{hostname}" if hostname else None


def healthy(base_url: str) -> bool:
    return httpx.get(f"{base_url}/api/health", timeout=5).status_code == 200


def register(graph: str, env: dict[str, str], callback: str) -> None:
    app_id, waba_id = env["WHATSAPP_APP_ID"], env["WHATSAPP_BUSINESS_ACCOUNT_ID"]
    with httpx.Client(timeout=30) as client:
        # Meta calls the callback with the verify token before accepting it.
        resp = client.post(
            f"{graph}/{app_id}/subscriptions",
            data={
                "object": "whatsapp_business_account",
                "callback_url": callback,
                "verify_token": env["WHATSAPP_VERIFY_TOKEN"],
                "fields": "messages",
                "access_token": f"{app_id}|{env['WHATSAPP_APP_SECRET']}",
            },
        )
        if resp.is_error:
            raise RuntimeError(f"Meta rejected the webhook (HTTP {resp.status_code}): {resp.text[:400]}")
        resp = client.post(
            f"{graph}/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {env['WHATSAPP_ACCESS_TOKEN']}"},
        )
        if resp.is_error:
            raise RuntimeError(
                f"Couldn't subscribe the app to the WhatsApp account (HTTP {resp.status_code}): {resp.text[:400]}"
            )


def phone_numbers(graph: str, env: dict[str, str]) -> list[str]:
    resp = httpx.get(
        f"{graph}/{env['WHATSAPP_BUSINESS_ACCOUNT_ID']}/phone_numbers",
        params={"fields": "display_phone_number"},
        headers={"Authorization": f"Bearer {env['WHATSAPP_ACCESS_TOKEN']}"},
        timeout=15,
    )
    return [p["display_phone_number"] for p in resp.json().get("data", [])] if resp.is_success else []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Public base URL (default: the quick tunnel's)")
    parser.add_argument("--metrics", default="127.0.0.1:20249", help="cloudflared metrics address")
    parser.add_argument("--port", type=int, default=8000, help="Local backend port")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the backend and tunnel to come up first; skip quietly if WhatsApp isn't configured",
    )
    args = parser.parse_args()

    load_env()
    env = {name: os.getenv(name, "") for name in REQUIRED}
    missing = [name for name, value in env.items() if not value]
    if missing:
        if args.wait:
            say(f"WhatsApp not configured ({', '.join(missing)} missing in .env). Skipping.")
            return
        sys.exit(f"[webhook] Missing in {ROOT_ENV}: {', '.join(missing)}")
    graph = f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_VERSION') or 'v25.0'}"

    if args.url:
        base = args.url.rstrip("/")
    elif args.wait:
        base = wait_for("the tunnel", lambda: tunnel_hostname(args.metrics), timeout=60)
    else:
        try:
            base = tunnel_hostname(args.metrics)
        except (httpx.HTTPError, ValueError):
            base = None
        if not base:
            sys.exit("[webhook] No tunnel running. Start `make tunnel` first, or pass URL=https://...")

    if args.wait:
        say("Waiting for the backend and the tunnel to be reachable…")
        wait_for("the local backend", lambda: healthy(f"http://127.0.0.1:{args.port}"), timeout=60)
        # A brand-new quick tunnel can take a few seconds before its DNS resolves.
        wait_for(f"{base} to be reachable", lambda: healthy(base), timeout=90, interval=3)

    callback = base + WEBHOOK_PATH
    attempts = 3 if args.wait else 1
    for attempt in range(1, attempts + 1):
        try:
            register(graph, env, callback)
            break
        except (RuntimeError, httpx.HTTPError) as exc:
            if attempt == attempts:
                sys.exit(f"[webhook] {exc}\n[webhook] Is the backend running and the tunnel up?")
            time.sleep(5)

    say(f"Registered {callback}")
    numbers = phone_numbers(graph, env)
    say(f"WhatsApp is live. Message {', '.join(numbers) or 'your WhatsApp number'} to check a draft.")


if __name__ == "__main__":
    main()
