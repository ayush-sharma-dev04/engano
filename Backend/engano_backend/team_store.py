"""Accounts, workspaces and the review pipeline, stored in one SQLite file.

This is the shared state behind the web studio: who can sign in, which workspaces exist, what
creators submitted and what reviewers decided. It uses only the standard library so it runs
anywhere the backend does. Every public method is a short transaction; callers pass the id of
the person acting and the store refuses anything that person may not do (it raises `Refused`
with a message that is safe to show).
"""

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

PURPOSES = ("Content Creator", "Business", "Reviewer")
SESSION_SECONDS = 14 * 24 * 3600
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  purpose TEXT NOT NULL,
  brand TEXT COLLATE NOCASE,
  salt TEXT NOT NULL,
  hash TEXT NOT NULL,
  created_by TEXT,
  created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS accounts_brand ON accounts(brand) WHERE brand IS NOT NULL;
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workspaces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  code TEXT NOT NULL UNIQUE,
  created_by TEXT NOT NULL REFERENCES accounts(id),
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('Creator', 'Reviewer')),
  UNIQUE (workspace_id, user_id)
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  UNIQUE (user_id)
);
CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  due_date TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS guidelines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('DO', 'DON''T')),
  text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  creator_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  findings TEXT NOT NULL,
  status TEXT NOT NULL,
  approved_by TEXT,
  reviewer_comment TEXT,
  ai_status TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviewer_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  workspace_id INTEGER NOT NULL,
  reviewer_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  action TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


class Refused(Exception):
    """The request is not allowed or not valid. The message is safe to show the person."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


class TeamStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self._tx() as db:
            db.executescript(SCHEMA)
            cols = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
            for extra in ("whatsapp", "discord_id"):
                if extra not in cols:
                    db.execute(f"ALTER TABLE accounts ADD COLUMN {extra} TEXT")
            if "supabase_id" not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN supabase_id TEXT")
            if not db.execute("SELECT 1 FROM meta WHERE key='receipt_secret'").fetchone():
                db.execute("INSERT INTO meta VALUES ('receipt_secret', ?)", (secrets.token_hex(32),))

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        db = self._memory or sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        if not self._memory:
            db.execute("PRAGMA journal_mode = WAL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            if not self._memory:
                db.close()

    # ------------------------------------------------------------ review receipts

    def _secret(self, db: sqlite3.Connection) -> bytes:
        return db.execute("SELECT value FROM meta WHERE key='receipt_secret'").fetchone()[0].encode()

    def review_scope(self, account_id: str) -> tuple[int | None, list[dict], str]:
        """The workspace a creator writes for, its DO/DON'T rules, and a fingerprint of both.

        A review receipt is tied to this fingerprint, so a review done without the workspace's rules
        (or before they changed) can never clear a draft.
        """
        with self._tx() as db:
            if self._purpose(db, account_id) != "Content Creator":
                return None, [], ""
            member = self._membership(db, account_id)
            if not member:
                return None, [], ""
            rules = [
                {"type": g["kind"], "text": g["text"]}
                for g in db.execute("SELECT kind, text FROM guidelines WHERE workspace_id = ? ORDER BY id", (member["workspace_id"],))
            ]
            digest = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()
            return int(member["workspace_id"]), rules, f"{member['workspace_id']}:{digest}"

    def make_receipt(self, text: str, clean: bool, scope: str = "") -> str:
        """Proof that ENGANO reviewed exactly this text (with these workspace rules) and found it clean or not."""
        with self._tx() as db:
            body = f"{hashlib.sha256(text.strip().encode()).hexdigest()}|{'clean' if clean else 'flagged'}|{scope}"
            return hmac.new(self._secret(db), body.encode(), hashlib.sha256).hexdigest() + ("c" if clean else "f")

    def receipt_is_clean(self, text: str, receipt: str | None, scope: str = "") -> bool:
        if not receipt or receipt[-1:] != "c":
            return False
        return hmac.compare_digest(self.make_receipt(text, True, scope), receipt)

    # ------------------------------------------------------------------- accounts

    def _new_account(
        self, db: sqlite3.Connection, name: str, email: str, password: str, purpose: str, brand: str | None, created_by: str | None
    ) -> str:
        name, email = name.strip(), email.strip()
        if not 2 <= len(name) <= 60:
            raise Refused("Enter a name of 2 to 60 characters.")
        if not EMAIL_RE.match(email) or len(email) > 120:
            raise Refused("Enter a valid email address.")
        if len(password) < 8 or len(password) > 200:
            raise Refused("Password must be at least 8 characters.")
        if purpose not in PURPOSES:
            raise Refused("Unknown account type.")
        if purpose == "Business":
            brand = (brand or "").strip()
            if not 2 <= len(brand) <= 60:
                raise Refused("Give your brand a name of 2 to 60 characters.")
            if db.execute("SELECT 1 FROM accounts WHERE brand = ?", (brand,)).fetchone():
                raise Refused("A brand with that name already exists. Use a more specific name.")
        else:
            brand = None
        if db.execute("SELECT 1 FROM accounts WHERE email = ?", (email,)).fetchone():
            raise Refused("An account with that email already exists. Sign in instead.", 409)
        account_id = f"u_{secrets.token_hex(6)}"
        salt = secrets.token_hex(16)
        db.execute(
            "INSERT INTO accounts (id, name, email, purpose, brand, salt, hash, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (account_id, name, email, purpose, brand, salt, _hash(password, salt), created_by, time.time()),
        )
        return account_id

    def _session(self, db: sqlite3.Connection, account_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (_token_hash(token), account_id, now + SESSION_SECONDS))
        return token

    def sign_up(self, name: str, email: str, password: str, purpose: str, brand: str | None) -> tuple[str, dict]:
        if purpose == "Reviewer":
            raise Refused("Reviewer accounts are created by a Brand Manager.", 403)
        with self._tx() as db:
            account_id = self._new_account(db, name, email, password, purpose, brand, None)
            return self._session(db, account_id), self._me(db, account_id)

    def sign_in(self, email: str, password: str) -> tuple[str, dict]:
        with self._tx() as db:
            row = db.execute("SELECT * FROM accounts WHERE email = ?", (email.strip(),)).fetchone()
            # Same work and same message whether or not the email exists.
            salt = row["salt"] if row else "00" * 16
            ok = hmac.compare_digest(_hash(password, salt), row["hash"] if row else "0" * 64)
            if not row or not ok:
                raise Refused("Wrong email or password.", 401)
            return self._session(db, row["id"]), self._me(db, row["id"])

    def sign_out(self, token: str) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def account_for(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._tx() as db:
            row = db.execute(
                "SELECT a.id FROM sessions s JOIN accounts a ON a.id = s.account_id WHERE s.token_hash = ? AND s.expires_at > ?",
                (_token_hash(token), time.time()),
            ).fetchone()
            return self._me(db, row["id"]) if row else None

    def accounts_to_mirror(self) -> list[dict]:
        with self._tx() as db:
            rows = db.execute("SELECT id, name, email, purpose, brand FROM accounts WHERE supabase_id IS NULL ORDER BY created_at").fetchall()
            return [dict(r) for r in rows]

    def set_supabase_id(self, account_id: str, supabase_id: str) -> None:
        with self._tx() as db:
            db.execute("UPDATE accounts SET supabase_id = ? WHERE id = ?", (supabase_id, account_id))

    def _me(self, db: sqlite3.Connection, account_id: str) -> dict:
        r = db.execute("SELECT id, name, email, purpose, brand, whatsapp, discord_id FROM accounts WHERE id = ?", (account_id,)).fetchone()
        me = {k: r[k] for k in ("id", "name", "email", "purpose", "brand")}
        me["whatsapp"] = r["whatsapp"] or ""
        me["discordId"] = r["discord_id"] or ""
        return me

    def set_contact(self, account_id: str, whatsapp: str | None, discord_id: str | None) -> dict:
        """Save where this person wants to be messaged. Both are optional; blank clears one."""
        with self._tx() as db:
            if self._purpose(db, account_id) != "Reviewer":
                raise Refused("Only reviewers receive review messages.", 403)
            db.execute("UPDATE accounts SET whatsapp = ?, discord_id = ? WHERE id = ?", (whatsapp or None, discord_id or None, account_id))
            return self._me(db, account_id)

    def contact_of(self, account_id: str) -> dict:
        with self._tx() as db:
            r = db.execute("SELECT whatsapp, discord_id FROM accounts WHERE id = ?", (account_id,)).fetchone()
            return {"whatsapp": r["whatsapp"], "discord_id": r["discord_id"]}

    def reviewer_contacts(self, workspace_id: int) -> list[dict]:
        """Reviewers of a workspace who saved at least one way to be messaged."""
        with self._tx() as db:
            rows = db.execute(
                "SELECT a.id, a.name, a.whatsapp, a.discord_id FROM members m JOIN accounts a ON a.id = m.user_id "
                "WHERE m.workspace_id = ? AND m.role = 'Reviewer' AND (a.whatsapp IS NOT NULL OR a.discord_id IS NOT NULL)",
                (workspace_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def workspace_name(self, workspace_id: int) -> str:
        with self._tx() as db:
            r = db.execute("SELECT name FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
            return r["name"] if r else ""

    def name_of(self, account_id: str) -> str:
        with self._tx() as db:
            r = db.execute("SELECT name FROM accounts WHERE id = ?", (account_id,)).fetchone()
            return r["name"] if r else ""

    # ----------------------------------------------------------------- guards

    @staticmethod
    def _owned(db: sqlite3.Connection, workspace_id: int, manager_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM workspaces WHERE id = ? AND created_by = ?", (workspace_id, manager_id)).fetchone()
        if not row:
            raise Refused("That workspace was not found.", 404)
        return row

    @staticmethod
    def _purpose(db: sqlite3.Connection, account_id: str) -> str:
        return db.execute("SELECT purpose FROM accounts WHERE id = ?", (account_id,)).fetchone()["purpose"]

    def _need(self, db: sqlite3.Connection, account_id: str, purpose: str, doing: str) -> None:
        if self._purpose(db, account_id) != purpose:
            raise Refused(f"Only a {'Brand Manager' if purpose == 'Business' else purpose.lower()} can {doing}.", 403)

    @staticmethod
    def _membership(db: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
        return db.execute(
            "SELECT m.*, w.name AS workspace_name FROM members m JOIN workspaces w ON w.id = m.workspace_id WHERE m.user_id = ? ORDER BY m.id LIMIT 1",
            (user_id,),
        ).fetchone()

    # -------------------------------------------------------------- workspaces

    def create_workspace(self, manager_id: str, name: str) -> int:
        name = name.strip()
        if not 2 <= len(name) <= 80:
            raise Refused("Enter a workspace name of 2 to 80 characters.")
        with self._tx() as db:
            self._need(db, manager_id, "Business", "create workspaces")
            for _ in range(20):
                code = "ENG-" + "".join(secrets.choice(CODE_CHARS) for _ in range(6))
                if not db.execute("SELECT 1 FROM workspaces WHERE code = ?", (code,)).fetchone():
                    break
            cur = db.execute(
                "INSERT INTO workspaces (name, code, created_by, created_at) VALUES (?,?,?,?)", (name, code, manager_id, time.time())
            )
            return int(cur.lastrowid)

    def delete_workspace(self, manager_id: str, workspace_id: int) -> None:
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            db.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))

    def join_by_code(self, user_id: str, code: str) -> None:
        with self._tx() as db:
            self._need(db, user_id, "Content Creator", "join with a code")
            ws = db.execute("SELECT * FROM workspaces WHERE code = ?", (code.strip().upper(),)).fetchone()
            if not ws:
                raise Refused("Invalid workspace code. Ask your Brand Manager for the correct code.", 404)
            current = self._membership(db, user_id)
            if current and current["workspace_id"] != ws["id"]:
                raise Refused(f"You are already in {current['workspace_name']}. Leave it first to join another workspace.", 409)
            db.execute("DELETE FROM requests WHERE user_id = ?", (user_id,))
            db.execute("INSERT OR IGNORE INTO members (workspace_id, user_id, role) VALUES (?,?, 'Creator')", (ws["id"], user_id))

    def request_join(self, user_id: str, workspace_id: int) -> None:
        with self._tx() as db:
            self._need(db, user_id, "Content Creator", "ask to join a workspace")
            if not db.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
                raise Refused("That workspace was not found.", 404)
            current = self._membership(db, user_id)
            if current:
                raise Refused(f"You are already in {current['workspace_name']}. Leave it first to join another workspace.", 409)
            pending = db.execute(
                "SELECT w.name FROM requests r JOIN workspaces w ON w.id = r.workspace_id WHERE r.user_id = ?", (user_id,)
            ).fetchone()
            if pending:
                raise Refused(f"You already asked to join {pending['name']}. Cancel that request first.", 409)
            db.execute("INSERT INTO requests (workspace_id, user_id) VALUES (?,?)", (workspace_id, user_id))

    def cancel_request(self, user_id: str) -> None:
        with self._tx() as db:
            db.execute("DELETE FROM requests WHERE user_id = ?", (user_id,))

    def answer_request(self, manager_id: str, workspace_id: int, request_id: int, accept: bool) -> None:
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            req = db.execute("SELECT * FROM requests WHERE id = ? AND workspace_id = ?", (request_id, workspace_id)).fetchone()
            if not req:
                raise Refused("That request is no longer there.", 404)
            db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
            if accept and not self._membership(db, req["user_id"]):
                db.execute("INSERT INTO members (workspace_id, user_id, role) VALUES (?,?, 'Creator')", (workspace_id, req["user_id"]))

    def leave(self, user_id: str) -> None:
        with self._tx() as db:
            self._need(db, user_id, "Content Creator", "leave a workspace this way")
            db.execute("DELETE FROM members WHERE user_id = ?", (user_id,))

    def remove_member(self, manager_id: str, workspace_id: int, member_id: int) -> None:
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            db.execute("DELETE FROM members WHERE id = ? AND workspace_id = ?", (member_id, workspace_id))

    def create_reviewer(self, manager_id: str, workspace_id: int, name: str, email: str) -> dict:
        """Create a reviewer account with a generated password (returned once) and add it."""
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        password = "".join(secrets.choice(alphabet) for _ in range(10))
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            reviewer_id = self._new_account(db, name, email, password, "Reviewer", None, manager_id)
            db.execute("INSERT INTO members (workspace_id, user_id, role) VALUES (?,?, 'Reviewer')", (workspace_id, reviewer_id))
        return {"id": reviewer_id, "email": email.strip(), "password": password}

    def add_reviewer(self, manager_id: str, workspace_id: int, reviewer_id: str) -> None:
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            ok = db.execute(
                "SELECT 1 FROM accounts WHERE id = ? AND purpose = 'Reviewer' AND created_by = ?", (reviewer_id, manager_id)
            ).fetchone()
            if not ok:
                raise Refused("That reviewer was not found.", 404)
            db.execute("INSERT OR IGNORE INTO members (workspace_id, user_id, role) VALUES (?,?, 'Reviewer')", (workspace_id, reviewer_id))

    # ------------------------------------------------------ assignments, guidelines

    def add_assignment(self, manager_id: str, workspace_id: int, title: str, description: str, due: str) -> None:
        self._check_assignment(title, description, due)
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            db.execute(
                "INSERT INTO assignments (workspace_id, title, description, due_date, created_at) VALUES (?,?,?,?,?)",
                (workspace_id, title.strip(), description.strip(), due, time.time()),
            )

    def update_assignment(self, manager_id: str, assignment_id: int, title: str, description: str, due: str) -> None:
        self._check_assignment(title, description, due)
        with self._tx() as db:
            row = db.execute(
                "SELECT a.id FROM assignments a JOIN workspaces w ON w.id = a.workspace_id WHERE a.id = ? AND w.created_by = ?",
                (assignment_id, manager_id),
            ).fetchone()
            if not row:
                raise Refused("That assignment was not found.", 404)
            db.execute(
                "UPDATE assignments SET title=?, description=?, due_date=? WHERE id=?",
                (title.strip(), description.strip(), due, assignment_id),
            )

    def delete_assignment(self, manager_id: str, assignment_id: int) -> None:
        with self._tx() as db:
            db.execute(
                "DELETE FROM assignments WHERE id = ? AND workspace_id IN (SELECT id FROM workspaces WHERE created_by = ?)",
                (assignment_id, manager_id),
            )

    @staticmethod
    def _check_assignment(title: str, description: str, due: str) -> None:
        if not 1 <= len(title.strip()) <= 120:
            raise Refused("Enter an assignment title of up to 120 characters.")
        if len(description) > 4000:
            raise Refused("The assignment details are too long.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            raise Refused("Choose a due date.")

    def set_guidelines(self, manager_id: str, workspace_id: int, items: list[dict]) -> None:
        if len(items) > 200:
            raise Refused("Too many guidelines.")
        clean = []
        for item in items:
            text = str(item.get("text", "")).strip()
            kind = item.get("type")
            if kind not in ("DO", "DON'T") or not 1 <= len(text) <= 500:
                raise Refused("Each guideline needs a DO or DON'T type and up to 500 characters of text.")
            clean.append((kind, text))
        with self._tx() as db:
            self._owned(db, workspace_id, manager_id)
            db.execute("DELETE FROM guidelines WHERE workspace_id = ?", (workspace_id,))
            db.executemany("INSERT INTO guidelines (workspace_id, kind, text) VALUES (?,?,?)", [(workspace_id, k, t) for k, t in clean])

    # ------------------------------------------------------------ submissions

    def submit(
        self, creator_id: str, title: str, content: str, findings: list, ai_status: str | None, receipt: str | None, editing_id: int | None
    ) -> dict:
        content = content.strip()
        if not content:
            raise Refused("There is nothing to submit.")
        if len(content) > 10_000 or len(json.dumps(findings)) > 400_000 or len(findings) > 200:
            raise Refused("That draft is too large to submit.")
        cleared = self.receipt_is_clean(content, receipt, self.review_scope(creator_id)[2])
        with self._tx() as db:
            self._need(db, creator_id, "Content Creator", "submit drafts")
            member = self._membership(db, creator_id)
            if not member:
                raise Refused("Join a workspace before submitting.", 403)
            fields = (
                (title.strip() or "Untitled Draft")[:120],
                content,
                json.dumps(findings),
                "Approved" if cleared else "Pending Review",
                "AI" if cleared else None,
                ai_status if ai_status in ("GREEN", "YELLOW", "RED") else None,
            )
            now = time.time()
            if editing_id is not None:
                row = db.execute("SELECT * FROM submissions WHERE id = ? AND creator_id = ?", (editing_id, creator_id)).fetchone()
                if not row or row["status"] == "Approved":
                    raise Refused("That draft can no longer be edited.", 409)
                db.execute(
                    "UPDATE submissions SET title=?, content=?, findings=?, status=?, approved_by=?, ai_status=?, reviewer_comment=NULL, workspace_id=?, updated_at=? WHERE id=?",
                    (*fields, member["workspace_id"], now, editing_id),
                )
                sid = editing_id
            else:
                cur = db.execute(
                    "INSERT INTO submissions (title, content, findings, status, approved_by, ai_status, workspace_id, creator_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (*fields, member["workspace_id"], creator_id, now, now),
                )
                sid = int(cur.lastrowid)
            return self._submission(db, sid)

    def decide(self, reviewer_id: str, submission_id: int, approve: bool, comment: str = "") -> None:
        if not approve and not comment.strip():
            raise Refused("Say what the creator should change.")
        with self._tx() as db:
            self._need(db, reviewer_id, "Reviewer", "decide on drafts")
            sub = db.execute(
                "SELECT s.* FROM submissions s JOIN members m ON m.workspace_id = s.workspace_id AND m.user_id = ? AND m.role = 'Reviewer' WHERE s.id = ?",
                (reviewer_id, submission_id),
            ).fetchone()
            if not sub:
                raise Refused("That draft was not found.", 404)
            if sub["status"] != "Pending Review":
                raise Refused("That draft has already been decided.", 409)
            if approve:
                db.execute("UPDATE submissions SET status='Approved', approved_by='Reviewer', reviewer_comment=NULL, updated_at=? WHERE id=?", (time.time(), submission_id))
            else:
                db.execute(
                    "UPDATE submissions SET status='Changes Requested', approved_by=NULL, reviewer_comment=?, updated_at=? WHERE id=?",
                    (comment.strip()[:2000], time.time(), submission_id),
                )
            db.execute(
                "INSERT INTO reviewer_actions (submission_id, workspace_id, reviewer_id, title, action, created_at) VALUES (?,?,?,?,?,?)",
                (submission_id, sub["workspace_id"], reviewer_id, sub["title"], "Direct Approval" if approve else "Request Changes", time.time()),
            )

    # ---------------------------------------------------------------- reading

    def _submission(self, db: sqlite3.Connection, submission_id: int) -> dict:
        return self._sub_dict(db.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone())

    @staticmethod
    def _sub_dict(r: sqlite3.Row) -> dict:
        return {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "findings": json.loads(r["findings"]),
            "status": r["status"],
            "submittedAt": time.strftime("%d/%m/%Y %H:%M", time.localtime(r["created_at"])),
            "reviewerComment": r["reviewer_comment"],
            "workspaceId": r["workspace_id"],
            "creatorId": r["creator_id"],
            "approvedBy": r["approved_by"],
            "aiStatus": r["ai_status"],
            "at": _ms(r["created_at"]),
        }

    def snapshot(self, account_id: str) -> dict:
        """Everything this person may see, shaped the way the web studio uses it."""
        with self._tx() as db:
            me = self._me(db, account_id)
            purpose = me["purpose"]
            if purpose == "Business":
                ws_rows = db.execute("SELECT * FROM workspaces WHERE created_by = ? ORDER BY id DESC", (account_id,)).fetchall()
            else:
                ws_rows = db.execute(
                    "SELECT w.* FROM workspaces w JOIN members m ON m.workspace_id = w.id WHERE m.user_id = ? ORDER BY m.id", (account_id,)
                ).fetchall()
            ids = [w["id"] for w in ws_rows]
            marks = ",".join("?" * len(ids)) or "NULL"

            members = db.execute(f"SELECT * FROM members WHERE workspace_id IN ({marks}) ORDER BY id", ids).fetchall()
            requests = db.execute(f"SELECT * FROM requests WHERE workspace_id IN ({marks}) ORDER BY id", ids).fetchall() if purpose == "Business" else []
            workspaces = []
            for w in ws_rows:
                workspaces.append(
                    {
                        "id": w["id"],
                        "name": w["name"],
                        # Only the manager sees the join code.
                        "code": w["code"] if purpose == "Business" else "",
                        "createdAt": time.strftime("%d/%m/%Y", time.localtime(w["created_at"])),
                        "createdBy": w["created_by"],
                        "members": [
                            {"id": m["id"], "userId": m["user_id"], "role": m["role"]}
                            for m in members
                            if m["workspace_id"] == w["id"] and (purpose != "Content Creator" or m["user_id"] == account_id)
                        ],
                        "requests": [{"id": r["id"], "userId": r["user_id"]} for r in requests if r["workspace_id"] == w["id"]],
                    }
                )

            assignments = [
                {"id": a["id"], "workspaceId": a["workspace_id"], "title": a["title"], "description": a["description"],
                 "dueDate": a["due_date"], "createdAt": time.strftime("%d/%m/%Y", time.localtime(a["created_at"]))}
                for a in db.execute(f"SELECT * FROM assignments WHERE workspace_id IN ({marks}) ORDER BY id DESC", ids)
            ]
            guidelines: dict[str, list] = {str(i): [] for i in ids}
            for g in db.execute(f"SELECT * FROM guidelines WHERE workspace_id IN ({marks}) ORDER BY id", ids):
                guidelines[str(g["workspace_id"])].append({"id": g["id"], "type": g["kind"], "text": g["text"]})

            if purpose == "Content Creator":
                subs = db.execute("SELECT * FROM submissions WHERE creator_id = ? ORDER BY id DESC", (account_id,)).fetchall()
            else:
                subs = db.execute(f"SELECT * FROM submissions WHERE workspace_id IN ({marks}) ORDER BY id DESC", ids).fetchall()
            actions = [
                {"id": a["id"], "submissionId": a["submission_id"], "workspaceId": a["workspace_id"], "title": a["title"],
                 "action": a["action"], "createdAt": "", "reviewerId": a["reviewer_id"], "at": _ms(a["created_at"])}
                for a in db.execute(f"SELECT * FROM reviewer_actions WHERE workspace_id IN ({marks}) ORDER BY id DESC", ids)
                if purpose != "Reviewer" or a["reviewer_id"] == account_id
            ] if purpose != "Content Creator" else []
            # Names for everyone this person can see; ids themselves are never shown.
            wanted = {m["user_id"] for m in members} | {s["creator_id"] for s in subs} | {a["reviewerId"] for a in actions}
            wanted |= {r["user_id"] for r in requests} | {w["created_by"] for w in ws_rows} | {account_id}
            people = {}
            for pid in wanted:
                row = db.execute("SELECT name FROM accounts WHERE id = ?", (pid,)).fetchone()
                if row:
                    people[pid] = row["name"]

            directory = []
            my_reviewers = []
            if purpose == "Content Creator":
                for m in db.execute("SELECT id, name, brand FROM accounts WHERE purpose = 'Business' ORDER BY brand"):
                    spaces = db.execute("SELECT id, name FROM workspaces WHERE created_by = ? ORDER BY id", (m["id"],)).fetchall()
                    directory.append(
                        {"managerId": m["id"], "managerName": m["name"], "brand": m["brand"],
                         "workspaces": [{"id": s["id"], "name": s["name"]} for s in spaces]}
                    )
                pending = db.execute(
                    "SELECT w.id, w.name FROM requests r JOIN workspaces w ON w.id = r.workspace_id WHERE r.user_id = ?", (account_id,)
                ).fetchone()
            else:
                pending = None
            if purpose == "Business":
                my_reviewers = [
                    {"id": r["id"], "name": r["name"], "email": r["email"]}
                    for r in db.execute("SELECT id, name, email FROM accounts WHERE purpose = 'Reviewer' AND created_by = ? ORDER BY name", (account_id,))
                ]
            return {
                "me": me,
                "people": people,
                "workspaces": workspaces,
                "assignments": assignments,
                "guidelines": guidelines,
                "submissions": [self._sub_dict(s) for s in subs],
                "reviewerActions": actions,
                "directory": directory,
                "pendingRequest": {"id": pending["id"], "name": pending["name"]} if pending else None,
                "myReviewers": my_reviewers,
            }
