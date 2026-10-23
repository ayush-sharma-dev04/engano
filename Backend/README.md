# ENGANO backend

FastAPI app (`main.py` → `engano_backend/app.py`). For now it hosts:

| Route | What it does |
|---|---|
| `GET /api/health` | Status, active brand and policy source, whether WhatsApp is configured |
| `GET /api/webhooks/whatsapp` | Meta's webhook verification handshake |
| `POST /api/webhooks/whatsapp` | Incoming WhatsApp messages: review the text, reply in the chat |

`engano_backend/review_service.py` is the shared bridge to `ai_engine`, used by both this app and the Discord bot. It picks the brand (`ENGANO_BRAND_ID`) and the policy source (`ENGANO_POLICY_SOURCE`: `supabase`, or `fixture` for local testing).

## Run

```
make setup
make backend   # http://localhost:8000, or `make start` for everything
make test      # engine + backend tests
```

## WhatsApp: how it behaves

- **Text message:** reviewed. The reply quotes the message and gives 🟢/🟡/🔴, up to 5 findings with their cited rule and fix, and a suggested rewrite.
- **Image with caption:** the caption is reviewed; the image itself is not (image checks are in the studio).
- **Image without caption, voice note, etc.:** a short explanation of what can be checked.
- **`help` / `hi`:** how to use it.

Every POST must carry a valid `X-Hub-Signature-256` (HMAC of the body with the app secret), or it is refused. The webhook replies `200` straight away and does the review in the background, because Meta retries slow webhooks. Duplicate deliveries are ignored.

## WhatsApp: one-time Meta setup

1. **Meta app:** go to https://developers.facebook.com/apps and create an app (**Business** type) with the WhatsApp use case. Claim the free **test number** under WhatsApp → API Setup, and add the phones that will test it as **recipients** (up to 5).
2. **Permanent token:** in Business settings → **Users → System users**, add a system user (Admin). Assign it the app and the WhatsApp account with **Full control**. Then use **Generate new token** with expiry **Never** and the permissions `whatsapp_business_messaging` and `whatsapp_business_management`. The temporary tokens on the API Setup page expire after about 2 hours.
3. **Root `.env`:**
   ```
   WHATSAPP_ACCESS_TOKEN=<system-user token>
   WHATSAPP_APP_SECRET=<App settings → Basic → App secret>
   WHATSAPP_VERIFY_TOKEN=<any random string>
   WHATSAPP_APP_ID=<app ID>
   WHATSAPP_BUSINESS_ACCOUNT_ID=<"Messaging account ID" on the test number card>
   ```
   The backend reads `.env` only when it starts, so restart it after any change.

## WhatsApp: every time you start working

```
make start
```

This starts the Discord bot, the backend and a Cloudflare quick tunnel. When the tunnel is reachable (about 10–20 seconds), it registers the tunnel's new URL with Meta and prints:

```
[webhook] Registered https://<random>.trycloudflare.com/api/webhooks/whatsapp
[webhook] WhatsApp is live. Message +1 555-199-3735 to check a draft.
```

Then message the number from a verified phone: `help`, or a draft to check. If the tunnel drops while running, `make webhook` re-registers it without restarting anything.

## Troubleshooting

| Symptom | Cause |
|---|---|
| No reply, and no `POST /api/webhooks/whatsapp` in the backend log | The webhook points at an old tunnel URL. Restart `make start`, or run `make webhook` |
| `[webhook] WhatsApp not configured … Skipping.` | One of the `WHATSAPP_*` values is missing in `.env` |
| `(#131005) Access denied` in the log | Wrong or expired `WHATSAPP_ACCESS_TOKEN`, or the backend wasn't restarted after changing it |
| `Recipient phone number not in allowed list` | Add the phone as a recipient on the API Setup page (test numbers only) |
| `503` on POST | `WHATSAPP_APP_SECRET` not set |
