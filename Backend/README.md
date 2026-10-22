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

1. Go to https://developers.facebook.com/apps, then **Create app** → **Other** → **Business**. Add the **WhatsApp** product. Meta gives you a free test number.
2. **WhatsApp → API Setup**:
   - Copy the **temporary access token** into `WHATSAPP_ACCESS_TOKEN` in the root `.env`. It lasts 24 hours; use a system-user token for anything longer.
   - Under **To**, add and verify the phone numbers that will test it. The test number can only message up to 5 verified numbers.
3. **App settings → Basic**: copy the **App secret** into `WHATSAPP_APP_SECRET`.
4. Start the backend and a tunnel in two terminals:
   ```
   make backend
   make tunnel     # prints https://<random>.trycloudflare.com
   ```
5. **WhatsApp → Configuration → Webhook → Edit**:
   - **Callback URL:** `https://<random>.trycloudflare.com/api/webhooks/whatsapp`
   - **Verify token:** the value of `WHATSAPP_VERIFY_TOKEN` in `.env`.

   Click **Verify and save**, then **subscribe** to the `messages` field.
6. From a verified phone, message the test number. Send `help` first, then a draft.

The quick tunnel URL changes every time `make tunnel` starts, so update the callback URL in Meta when it does.
