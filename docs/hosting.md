# Hosting: web app on Netlify, backend on your computer

```
 people's browsers ──▶ Netlify (the web app, static files)
        │
        └──────────────▶ https://<tunnel>.trycloudflare.com ──▶ your computer: backend :8000
                                                                  ├─ Supabase (data, online)
                                                                  ├─ Ollama (AI, local)
                                                                  └─ Docker renderer (website checks, local)
```

The web app is only files. All the work (reviews, website checks, accounts) happens in the backend, so **your computer must be on
and `make start` running** whenever someone uses the site.

## 1. Backend (your computer)

1. In `.env` allow the hosted site to call the backend. `make start` already works with the pattern below, which covers any
   `*.netlify.app` site and its deploy previews; tighten it to your exact address once you know it:

   ```
   ENGANO_CORS_ORIGIN_REGEX=https://[a-z0-9-]+\.netlify\.app
   # or exactly:  ENGANO_CORS_ORIGINS=http://localhost:5173,https://your-site.netlify.app
   ```
   (Optional) `ENGANO_STUDIO_URL=https://your-site.netlify.app` so `make api-url` prints a ready-to-share link and the Discord bot's
   "Open in studio" button works.
2. `make start`. It starts the backend, the tunnel and everything else, and prints the public address:

   ```
   [api-url] Backend is public at  https://xxxx-xxxx.trycloudflare.com
   [api-url] Share this link:       https://your-site.netlify.app/?api=https://xxxx-xxxx.trycloudflare.com
   ```
   `make api-url` prints it again later.

Reviews and website checks require a signed-in person (`ENGANO_REQUIRE_LOGIN=1`, the default) and each person gets a fair share
(`ENGANO_REVIEW_LIMIT`, `ENGANO_SITE_LIMIT` per 10 minutes), because the backend is now reachable from the internet.

## 2. Netlify

1. Netlify > Add new site > Import from Git > this repository > the branch you want live (for example `main`).
2. Build settings come from `netlify.toml`: build command `npm --prefix Frontend ci && npm --prefix Frontend run build`, publish
   directory `Frontend/dist`, Node 22, and a rule that sends every path to `index.html` (so `/queue/12` survives a refresh).
   Leave Netlify's own build settings empty. No environment variables are needed.
3. Deploy.

## 3. Telling the site where the backend is (in `.env`)

Put it in the repo's `.env`, the same file as everything else:

```
VITE_API_URL=https://xxxx-xxxx.trycloudflare.com   # or leave empty to use the running tunnel
NETLIFY_AUTH_TOKEN=...                             # Netlify > User settings > Applications > new personal access token
NETLIFY_SITE_ID=...                                # Netlify > your site > Site configuration > Site ID
```

Then `make deploy` builds the web app with that address baked in and publishes it to your Netlify site (no Git push needed, no link
to open, nobody enters anything). If `VITE_API_URL` is empty, it uses the address of the tunnel that is running right now, so the
routine is: `make start`, then `make deploy`. A quick tunnel gets a **new address on every start**, so run `make deploy` again after
restarting it, or use a fixed tunnel (below) and set `VITE_API_URL` once.

Only variables starting with `VITE_` ever reach the website; the rest of `.env` (database URL, keys) stays on your computer.

Prefer the Netlify dashboard? Add `VITE_API_URL` under Site configuration > Environment variables and trigger a deploy (Netlify cannot
read your local `.env`, so the value has to be entered there too).

Fallback, if the site was published with a different address: the sign-in page has **Server > Change**, and a link with `?api=https://...`
suggests an address (the person must confirm it). `make api-url` prints that link.

## Want one fixed address instead?

Use a tunnel with a stable hostname, set `VITE_API_URL=https://that-address` in `.env` once and run `make deploy` once (or set it in Netlify
and redeploy); after that nothing changes when you restart. Options: a named Cloudflare tunnel on a domain you own, an ngrok free static
domain, or Tailscale Funnel. Point it at `http://localhost:8000`. WhatsApp's webhook can use the same address.

## Good to know

* Everyone signs in to the same Supabase data, from any device. Accounts and drafts do not depend on your computer; AI and website
  checks do.
* AI runs on your computer (Ollama). A slow machine means slow reviews for everyone. Website checks need the Docker renderer
  (`make renderer`).
* `http://` addresses are only accepted for `localhost`; a hosted (https) page cannot call other http addresses anyway.
* Never put `SUPABASE_*` keys or `.env` anywhere on Netlify: the site holds no secrets.
