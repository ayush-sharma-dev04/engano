"""Copy ENGANO accounts into Supabase Auth so they show under Authentication → Users.

ENGANO signs people in itself (see team_store); this only mirrors who exists. Two ways in:

* SUPABASE_SECRET_KEY: the Auth admin API creates a pre-confirmed user (preferred).
* SUPABASE_DB_URL: with no secret key, write the user straight into the project's `auth`
  tables over the database connection (the same thing the admin API does).

With neither it does nothing, and a failure here never blocks sign-up or sign-in.
"""

import logging
import os
import secrets
import uuid

import httpx

log = logging.getLogger("engano.auth_mirror")


class AuthMirror:
    def __init__(
        self, url: str | None, secret: str | None, client: httpx.Client | None = None, db_url: str | None = None
    ):
        self.url = (url or "").rstrip("/")
        self.secret = (secret or "").strip()
        self.db_url = (db_url or "").strip()
        self._client = client or httpx.Client(timeout=8.0)

    @classmethod
    def from_env(cls) -> "AuthMirror":
        return cls(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SECRET_KEY"), db_url=os.getenv("SUPABASE_DB_URL"))

    @property
    def enabled(self) -> bool:
        return bool((self.url and self.secret) or self.db_url)

    def push(self, account: dict, password: str | None = None) -> str | None:
        """Create the user in Supabase Auth. Returns its id, or None if skipped or refused."""
        if not self.enabled:
            return None
        if not (self.url and self.secret):
            return self._push_db(account, password)
        body = {
            "email": account["email"],
            "password": password or secrets.token_urlsafe(24),
            "email_confirm": True,
            "user_metadata": {
                "name": account["name"],
                "purpose": account["purpose"],
                "brand": account.get("brand"),
                "engano_account_id": account["id"],
            },
        }
        try:
            r = self._client.post(
                f"{self.url}/auth/v1/admin/users",
                json=body,
                headers={"apikey": self.secret, "Authorization": f"Bearer {self.secret}"},
            )
        except httpx.HTTPError as exc:
            log.warning("Supabase Auth mirror unreachable: %s", type(exc).__name__)
            return None
        if r.status_code in (200, 201):
            return r.json().get("id")
        # 422 "already registered" means it is already listed, which is what we want.
        log.warning("Supabase Auth mirror refused %s (HTTP %s)", account["email"], r.status_code)
        return None

    def _push_db(self, account: dict, password: str | None) -> str | None:
        """Insert the user into auth.users / auth.identities over the database connection."""
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError:
            log.warning("psycopg is not installed; cannot mirror accounts over SUPABASE_DB_URL")
            return None
        email = account["email"].strip()
        meta = {
            "name": account["name"],
            "purpose": account["purpose"],
            "brand": account.get("brand"),
            "engano_account_id": account["id"],
        }
        try:
            with psycopg.connect(self.db_url, connect_timeout=10) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM auth.users WHERE lower(email) = lower(%s)", (email,))
                existing = cur.fetchone()
                if existing:
                    return str(existing[0])
                new_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO auth.users (
                      instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
                      raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                      confirmation_token, recovery_token, email_change_token_new, email_change
                    ) VALUES (
                      '00000000-0000-0000-0000-000000000000', %s, 'authenticated', 'authenticated', %s,
                      extensions.crypt(%s, extensions.gen_salt('bf')), now(),
                      %s, %s, now(), now(), '', '', '', ''
                    )
                    """,
                    (
                        new_id,
                        email,
                        password or secrets.token_urlsafe(24),
                        Jsonb({"provider": "email", "providers": ["email"]}),
                        Jsonb(meta),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO auth.identities (id, provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'email', now(), now(), now())
                    """,
                    (str(uuid.uuid4()), new_id, new_id, Jsonb({"sub": new_id, "email": email, "email_verified": True})),
                )
                return new_id
        except Exception as exc:
            log.warning("Supabase Auth mirror (database) failed for %s: %s", email, type(exc).__name__)
            return None
