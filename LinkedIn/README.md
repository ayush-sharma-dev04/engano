# ENGANO LinkedIn adapter

The one channel where ENGANO also **publishes**, so it enforces the rule that nothing goes out unapproved. A post is published only when:

1. the review marks it **🟢 GREEN**, and
2. a named person is recorded as approving it (`approved_by`).

RED, YELLOW or incomplete reviews are refused with the findings, and nothing is posted. The FastAPI backend mounts these routes, so they run with `make start`.

| Route | |
|---|---|
| `GET /api/oauth/linkedin/start` | Sign in to LinkedIn and connect an account (`make linkedin` opens it) |
| `GET /api/oauth/linkedin/callback` | Where LinkedIn sends you back |
| `GET /api/linkedin/status` | Connected account, and who posts are published as |
| `POST /api/linkedin/check` `{"text"}` | Review only; never publishes |
| `POST /api/linkedin/publish` `{"text", "approved_by"}` | Review, then publish if GREEN |

```
curl -s localhost:8000/api/linkedin/check -H 'Content-Type: application/json' \
  -d '{"text": "Nimbus DB keeps your data safe with a 99.95% uptime SLA."}'

curl -s localhost:8000/api/linkedin/publish -H 'Content-Type: application/json' \
  -d '{"text": "Nimbus DB keeps your data safe with a 99.95% uptime SLA.", "approved_by": "Sankhyahrick"}'
```

When the web studio exists, its Approve button calls `/publish` with the reviewer's name.

## Setup (once)

1. Create an app at https://www.linkedin.com/developers/apps. LinkedIn requires a company page to link it to; any page you admin works.
2. On the **Products** tab, add **Sign In with LinkedIn using OpenID Connect** and **Share on LinkedIn**. Both are self-serve.
3. On the **Auth** tab, add the redirect URL `http://localhost:8000/api/oauth/linkedin/callback`, and copy the Client ID and Client Secret into the root `.env`:
   ```
   LINKEDIN_CLIENT_ID=...
   LINKEDIN_CLIENT_SECRET=...
   ```
4. Run `make start`, then `make linkedin`, and approve. The token is cached in `LinkedIn/.linkedin_token.json` (git-ignored, mode 600) and lasts about 60 days.

**Posting as a company page** needs LinkedIn to approve the **Community Management API** product for your app. Once approved, set `LINKEDIN_ORGANIZATION_ID` (the number in the page's admin URL) and reconnect. Until then, posts go out as the connected member.

| File | |
|---|---|
| `engano_linkedin/router.py` | Routes and the GREEN + approval gate |
| `engano_linkedin/client.py` | OAuth, profile lookup, Posts API (with LinkedIn's text escaping) |
| `engano_linkedin/token_store.py` | Local token cache |
| `engano_linkedin/config.py` | Settings and OAuth scopes |
