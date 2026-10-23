# ENGANO Gmail adapter

A review inbox. People forward a draft email or newsletter to it, or paste a draft into a new email. ENGANO replies **in the same thread** with the verdict, each finding with its cited rule and fix, and a suggested rewrite (plain text plus a formatted HTML version).

It checks the inbox over **IMAP every 15 seconds** and replies over **SMTP**. There's no webhook, tunnel or Google Cloud project: only a Gmail app password. Runs with `make start`, or on its own with `make gmail`.

## What gets reviewed

- **Forwarded email:** the forwarded message's subject and body. Your note above the forward is ignored.
- **New email:** the body, minus quoted replies (`> …`, "On … wrote:") and your signature (after `-- `).
- **HTML-only email:** converted to text first.
- **Images:** not checked (the reply says so); image checks run in the studio.
- **Empty email:** gets a how-to reply.
- **Never answered:** bounces, mailing lists, auto-replies, `no-reply` senders and its own address, so it can't get into reply loops. Every email is marked read once handled, even if handling fails.

## Setup (once)

1. Create a dedicated Gmail account for reviews, e.g. `engano.review@gmail.com`.
2. Turn on **2-Step Verification**: Google Account → Security.
3. Create an **app password** at https://myaccount.google.com/apppasswords (name it "ENGANO") and copy the 16 characters.
4. Add to the root `.env`:
   ```
   GMAIL_ADDRESS=engano.review@gmail.com
   GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
   GMAIL_ALLOWED_SENDERS=@yourcompany.com,teammate@gmail.com   # optional; empty = anyone
   ```
5. Run `make start` and look for `Watching engano.review@gmail.com every 15 s`.

If login fails, the account needs 2-Step Verification and an **app password**; your normal password won't work.

| File | |
|---|---|
| `engano_gmail/__main__.py` | Entry point (`python -m engano_gmail`) |
| `engano_gmail/worker.py` | Poll, review, reply in thread |
| `engano_gmail/parse.py` | Raw email → draft text (forwards, quotes, signatures, HTML) |
| `engano_gmail/render.py` | Review result → plain-text and HTML reply |
| `engano_gmail/mailbox.py` | IMAP/SMTP |
