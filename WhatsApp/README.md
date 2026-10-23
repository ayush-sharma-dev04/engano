# ENGANO WhatsApp adapter

Meta WhatsApp Cloud API webhook at `/api/webhooks/whatsapp`. The FastAPI backend (`Backend/`) mounts it, so it runs as part of `make start` and has no process of its own.

| File | |
|---|---|
| `engano_whatsapp/router.py` | Verification handshake (GET) and incoming messages (POST) |
| `engano_whatsapp/signature.py` | `X-Hub-Signature-256` check |
| `engano_whatsapp/payload.py` | Webhook JSON → `IncomingMessage` |
| `engano_whatsapp/render.py` | Review result → WhatsApp text |
| `engano_whatsapp/client.py` | Sends replies and read receipts |
| `engano_whatsapp/register_webhook.py` | Points Meta at the current tunnel URL (`make webhook`; `make start` runs it automatically) |

## how it behaves

- **Text message:** reviewed. The reply quotes the message and gives 🟢/🟡/🔴, up to 5 findings with their cited rule and fix, and a suggested rewrite.
- **Image (with or without caption):** the caption is reviewed as the post text, and the image goes through the engine's accessibility check. WhatsApp images carry no alt text, so expect an alt-text finding. Image contents aren't analysed yet.
- **Voice note, sticker, document, etc.:** a short explanation of what can be checked.

Every message goes through `ai_engine`'s WhatsApp adapter (`ReviewService.build_payload`) and the multi-agent review. When the engine suggests a rewrite, it re-checks it, and the reply says whether the rewrite passes.
- **`help` / `hi`:** how to use it.

Every POST must carry a valid `X-Hub-Signature-256` (HMAC of the body with the app secret), or it is refused. The webhook replies `200` straight away and does the review in the background, because Meta retries slow webhooks. Duplicate deliveries are ignored.

## one-time Meta setup

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

## every time you start working

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
