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

## 3. Pointing the site at the backend

A quick tunnel gets a **new address every time it starts**, so the site does not have it built in:

* Open the link `make api-url` printed (`https://your-site.netlify.app/?api=https://xxxx.trycloudflare.com`). The sign-in page asks
  you to confirm the server (a link can only suggest one: it never switches on its own) and remembers it in that browser.
* Or, on the sign-in page, under the form: **Server > Change**, paste the address, **Use this server**. The dot shows green when it
  answers.
* Anyone you invite does the same once, with the link. When you restart the tunnel, send the new link.

## Want one fixed address instead?

Use a tunnel with a stable hostname, then set `VITE_API_URL=https://that-address` in Netlify (Site configuration > Environment
variables) and redeploy; nobody has to enter anything. Options: a named Cloudflare tunnel on a domain you own, an ngrok free static
domain, or Tailscale Funnel. Point it at `http://localhost:8000`. WhatsApp's webhook can use the same address.

## Good to know

* Everyone signs in to the same Supabase data, from any device. Accounts and drafts do not depend on your computer; AI and website
  checks do.
* AI runs on your computer (Ollama). A slow machine means slow reviews for everyone. Website checks need the Docker renderer
  (`make renderer`).
* `http://` addresses are only accepted for `localhost`; a hosted (https) page cannot call other http addresses anyway.
* Never put `SUPABASE_*` keys or `.env` anywhere on Netlify: the site holds no secrets.
