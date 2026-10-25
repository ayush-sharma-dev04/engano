"""Accounts, workspaces and the review pipeline: who can do what."""

import os

import pytest
from starlette.testclient import TestClient

from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore
from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_backend.team_store import PgTeamStore, TeamStore

PW = "password123"

# Set ENGANO_TEST_PG_URL to run this whole file against Postgres in a throwaway schema.
import pathlib, secrets as _secrets  # noqa: E402

MIGRATION = pathlib.Path("supabase/migrations/20261025_000006_team_app.sql")
_SCHEMAS: list = []


def new_store(tmp_path, name="t.db"):
    url = os.getenv("ENGANO_TEST_PG_URL")
    if not url:
        return TeamStore(tmp_path / name)
    import psycopg

    schema = "engano_t_" + _secrets.token_hex(4)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
        conn.execute(f"SET search_path TO {schema}")
        conn.execute(MIGRATION.read_text())
    _SCHEMAS.append((url, schema))
    return PgTeamStore(url, schema)


@pytest.fixture(scope="module", autouse=True)
def _drop_scratch_schemas():
    yield
    if _SCHEMAS:
        import psycopg

        with psycopg.connect(_SCHEMAS[0][0], autocommit=True) as conn:
            for _, schema in _SCHEMAS:
                conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def make_client(tmp_path, db="t.db", **kw):
    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    service = ReviewService(
        ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo,
        memory_store=FileBrandMemoryStore(storage_dir=tmp_path),
    )
    return TestClient(create_app(review_service=service, engine_config=EngineConfig(), team_store=new_store(tmp_path, db), **kw))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    return make_client(tmp_path)


def sign_up(client, name, purpose, brand=None):
    r = client.post(
        "/api/auth/signup",
        json={"name": name, "email": f"{name.lower()}@x.com", "password": PW, "purpose": purpose, "brand": brand},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def team(client):
    """A manager with a workspace, a reviewer account, and a creator who joined by code."""
    boss = sign_up(client, "Boss", "Business", "Acme")
    ws = client.post("/api/app/workspaces", json={"name": "Team"}, headers=boss).json()["id"]
    reviewer = client.post(f"/api/app/workspaces/{ws}/reviewers", json={"name": "Rita", "email": "rita@x.com"}, headers=boss).json()
    code = client.get("/api/app/state", headers=boss).json()["workspaces"][0]["code"]
    kate = sign_up(client, "Kate", "Content Creator")
    assert client.post("/api/app/join", json={"code": code}, headers=kate).status_code == 200
    signin = client.post("/api/auth/signin", json={"email": "rita@x.com", "password": reviewer["password"]})
    assert signin.status_code == 200
    rita = {"Authorization": f"Bearer {signin.json()['token']}"}
    return boss, rita, kate, ws


def test_signup_signin_and_wrong_password(client):
    sign_up(client, "Kate", "Content Creator")
    assert client.post("/api/auth/signin", json={"email": "KATE@x.com", "password": PW}).status_code == 200
    bad = client.post("/api/auth/signin", json={"email": "kate@x.com", "password": "nope-nope"})
    assert (bad.status_code, bad.json()["detail"]) == (401, "Wrong email or password.")
    missing = client.post("/api/auth/signin", json={"email": "ghost@x.com", "password": PW})
    assert missing.json()["detail"] == bad.json()["detail"]


def test_signup_rules(client):
    sign_up(client, "Boss", "Business", "Acme")
    dup = client.post("/api/auth/signup", json={"name": "Boss", "email": "boss@x.com", "password": PW, "purpose": "Content Creator"})
    assert dup.status_code == 409
    brand = client.post("/api/auth/signup", json={"name": "Other", "email": "o@x.com", "password": PW, "purpose": "Business", "brand": "acme"})
    assert "brand" in brand.json()["detail"]
    short = client.post("/api/auth/signup", json={"name": "Kate", "email": "k@x.com", "password": "short", "purpose": "Content Creator"})
    assert short.status_code == 400
    no_brand = client.post("/api/auth/signup", json={"name": "Bo", "email": "b@x.com", "password": PW, "purpose": "Business"})
    assert no_brand.status_code == 400


def test_reviewers_cannot_sign_up(client):
    r = client.post("/api/auth/signup", json={"name": "Rita", "email": "r@x.com", "password": PW, "purpose": "Reviewer"})
    assert r.status_code == 403


def test_signin_is_throttled(client):
    sign_up(client, "Kate", "Content Creator")
    for _ in range(8):
        client.post("/api/auth/signin", json={"email": "kate@x.com", "password": "wrong-pass"})
    assert client.post("/api/auth/signin", json={"email": "kate@x.com", "password": PW}).status_code == 429


def test_signout_ends_the_session(client):
    h = sign_up(client, "Kate", "Content Creator")
    assert client.get("/api/app/state", headers=h).status_code == 200
    client.post("/api/auth/signout", headers=h)
    assert client.get("/api/app/state", headers=h).status_code == 401
    assert client.get("/api/app/state").status_code == 401


def test_reviewer_account_can_sign_in_from_anywhere(client):
    _, rita, _, _ = team(client)
    me = client.get("/api/app/state", headers=rita).json()["me"]
    assert me["purpose"] == "Reviewer"


def test_creator_never_sees_the_join_code_or_other_members(client):
    boss, _, kate, _ = team(client)
    mine = client.get("/api/app/state", headers=kate).json()["workspaces"][0]
    assert mine["code"] == ""
    assert [m["role"] for m in mine["members"]] == ["Creator"]
    assert client.get("/api/app/state", headers=boss).json()["workspaces"][0]["code"].startswith("ENG-")


def test_only_the_owner_manages_a_workspace(client):
    boss, rita, kate, ws = team(client)
    other = sign_up(client, "Other", "Business", "Other Co")
    for who in (kate, rita, other):
        assert client.delete(f"/api/app/workspaces/{ws}", headers=who).status_code in (403, 404)
        assert client.post(f"/api/app/workspaces/{ws}/assignments", json={"title": "x", "due_date": "2030-01-01"}, headers=who).status_code in (403, 404)
        assert client.put(f"/api/app/workspaces/{ws}/guidelines", json={"items": []}, headers=who).status_code in (403, 404)
    assert client.post("/api/app/workspaces", json={"name": "Mine"}, headers=kate).status_code == 403


def test_assignments_edit_delete_and_reach_the_creator(client):
    boss, _, kate, ws = team(client)
    client.post(f"/api/app/workspaces/{ws}/assignments", json={"title": "Launch", "description": "d", "due_date": "2030-01-01"}, headers=boss)
    aid = client.get("/api/app/state", headers=kate).json()["assignments"][0]["id"]
    client.put(f"/api/app/assignments/{aid}", json={"title": "Launch v2", "description": "d", "due_date": "2030-02-02"}, headers=boss)
    assert client.get("/api/app/state", headers=kate).json()["assignments"][0]["title"] == "Launch v2"
    assert client.put(f"/api/app/assignments/{aid}", json={"title": "x", "due_date": "2030-02-02"}, headers=kate).status_code == 404
    client.delete(f"/api/app/assignments/{aid}", headers=boss)
    assert client.get("/api/app/state", headers=kate).json()["assignments"] == []


def test_reviewer_add_remove_and_reuse(client):
    boss, rita, _, ws = team(client)
    members = client.get("/api/app/state", headers=boss).json()["workspaces"][0]["members"]
    rid = next(m["id"] for m in members if m["role"] == "Reviewer")
    client.delete(f"/api/app/workspaces/{ws}/members/{rid}", headers=boss)
    assert client.get("/api/app/state", headers=rita).json()["workspaces"] == []
    reviewer_id = client.get("/api/app/state", headers=boss).json()["myReviewers"][0]["id"]
    assert client.post(f"/api/app/workspaces/{ws}/reviewers/existing", json={"reviewer_id": reviewer_id}, headers=boss).status_code == 200
    assert len(client.get("/api/app/state", headers=rita).json()["workspaces"]) == 1
    stranger = sign_up(client, "Other", "Business", "Other Co")
    ws2 = client.post("/api/app/workspaces", json={"name": "W2"}, headers=stranger).json()["id"]
    assert client.post(f"/api/app/workspaces/{ws2}/reviewers/existing", json={"reviewer_id": reviewer_id}, headers=stranger).status_code == 404


def test_request_to_join_needs_the_managers_answer(client):
    boss, _, _, ws = team(client)
    dana = sign_up(client, "Dana", "Content Creator")
    assert client.post(f"/api/app/workspaces/{ws}/request", headers=dana).status_code == 200
    assert client.post(f"/api/app/workspaces/{ws}/request", headers=dana).status_code == 409
    state = client.get("/api/app/state", headers=boss).json()
    rid = state["workspaces"][0]["requests"][0]["id"]
    assert client.get("/api/app/state", headers=dana).json()["pendingRequest"]["id"] == ws
    assert client.post(f"/api/app/workspaces/{ws}/requests/{rid}", json={"accept": True}, headers=dana).status_code == 404
    client.post(f"/api/app/workspaces/{ws}/requests/{rid}", json={"accept": True}, headers=boss)
    assert client.get("/api/app/state", headers=dana).json()["pendingRequest"] is None
    assert len(client.get("/api/app/state", headers=dana).json()["workspaces"]) == 1


def test_a_creator_is_in_one_workspace_at_a_time(client):
    boss, _, kate, _ = team(client)
    ws2 = client.post("/api/app/workspaces", json={"name": "Second"}, headers=boss).json()["id"]
    code2 = next(w["code"] for w in client.get("/api/app/state", headers=boss).json()["workspaces"] if w["id"] == ws2)
    r = client.post("/api/app/join", json={"code": code2}, headers=kate)
    assert r.status_code == 409 and "already in" in r.json()["detail"]
    assert client.post("/api/app/join", json={"code": "ENG-NOPE00"}, headers=kate).status_code == 404
    client.post("/api/app/leave", headers=kate)
    assert client.post("/api/app/join", json={"code": code2}, headers=kate).status_code == 200


def review(client, text, headers=None):
    r = client.post("/api/review", json={"text": text}, headers=headers or {})
    assert r.status_code == 200
    return r.headers["X-Review-Receipt"], r.json()


CLEAN = "Nimbus DB is a reliable platform for modern teams."
BAD = "NimbusDB has 100% uptime. Try it free forever."


def test_clean_text_with_a_receipt_is_cleared_by_ai(client):
    _, _, kate, _ = team(client)
    receipt, body = review(client, CLEAN, kate)
    assert body["decision"]["status"] == "GREEN"
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN, "ai_status": "GREEN", "receipt": receipt}, headers=kate).json()
    assert (sub["status"], sub["approvedBy"]) == ("Approved", "AI")


def test_a_creator_cannot_fake_ai_clearance(client):
    _, _, kate, _ = team(client)
    flagged, _ = review(client, BAD, kate)
    clean_receipt, _ = review(client, CLEAN, kate)
    for receipt in (None, "", "deadbeefc", flagged, clean_receipt):
        sub = client.post(
            "/api/app/submissions", json={"title": "t", "content": BAD, "ai_status": "GREEN", "receipt": receipt}, headers=kate
        ).json()
        assert sub["status"] == "Pending Review", receipt
    # a clean receipt does not carry over to different text
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN + " Extra.", "receipt": clean_receipt}, headers=kate).json()
    assert sub["status"] == "Pending Review"


def test_review_flow_reject_resubmit_approve(client):
    boss, rita, kate, _ = team(client)
    sub = client.post("/api/app/submissions", json={"title": "Launch", "content": BAD, "ai_status": "RED"}, headers=kate).json()
    assert sub["status"] == "Pending Review"
    assert [s["id"] for s in client.get("/api/app/state", headers=rita).json()["submissions"]] == [sub["id"]]
    assert client.post(f"/api/app/submissions/{sub['id']}/approve", headers=kate).status_code == 403
    assert client.post(f"/api/app/submissions/{sub['id']}/approve", headers=boss).status_code == 403
    assert client.post(f"/api/app/submissions/{sub['id']}/reject", json={"comment": "  "}, headers=rita).status_code == 400
    client.post(f"/api/app/submissions/{sub['id']}/reject", json={"comment": "Remove the uptime claim."}, headers=rita)
    mine = client.get("/api/app/state", headers=kate).json()["submissions"][0]
    assert (mine["status"], mine["reviewerComment"]) == ("Changes Requested", "Remove the uptime claim.")
    receipt, _ = review(client, CLEAN, kate)
    again = client.post("/api/app/submissions", json={"title": "Launch", "content": CLEAN, "receipt": receipt, "editing_id": sub["id"]}, headers=kate).json()
    assert (again["id"], again["status"], again["approvedBy"]) == (sub["id"], "Approved", "AI")
    assert client.post("/api/app/submissions", json={"title": "x", "content": BAD, "editing_id": sub["id"]}, headers=kate).status_code == 409


def test_reviewer_decisions_are_logged_and_visible_to_the_manager(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    client.post(f"/api/app/submissions/{sid}/approve", headers=rita)
    assert client.post(f"/api/app/submissions/{sid}/approve", headers=rita).status_code == 409
    acts = client.get("/api/app/state", headers=boss).json()["reviewerActions"]
    assert [(a["action"], a["reviewerId"] is not None) for a in acts] == [("Direct Approval", True)]
    assert client.get("/api/app/state", headers=kate).json()["reviewerActions"] == []


def test_people_cannot_read_another_workspaces_data(client):
    boss, rita, kate, _ = team(client)
    client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate)
    other_boss = sign_up(client, "Other", "Business", "Other Co")
    other_ws = client.post("/api/app/workspaces", json={"name": "Elsewhere"}, headers=other_boss).json()["id"]
    snap = client.get("/api/app/state", headers=other_boss).json()
    assert [w["id"] for w in snap["workspaces"]] == [other_ws] and snap["submissions"] == []
    outsider = sign_up(client, "Out", "Content Creator")
    assert client.get("/api/app/state", headers=outsider).json()["submissions"] == []


def test_guidelines_round_trip_and_validation(client):
    boss, _, kate, ws = team(client)
    items = [{"type": "DON'T", "text": "Never say cheapest"}, {"type": "DO", "text": "Use Nimbus DB"}]
    assert client.put(f"/api/app/workspaces/{ws}/guidelines", json={"items": items}, headers=boss).status_code == 200
    got = client.get("/api/app/state", headers=kate).json()["guidelines"][str(ws)]
    assert [(g["type"], g["text"]) for g in got] == [("DON'T", "Never say cheapest"), ("DO", "Use Nimbus DB")]
    assert client.put(f"/api/app/workspaces/{ws}/guidelines", json={"items": [{"type": "MAYBE", "text": "x"}]}, headers=boss).status_code == 400


def test_directory_lists_brands_for_creators(client):
    team(client)
    dana = sign_up(client, "Dana", "Content Creator")
    d = client.get("/api/app/state", headers=dana).json()["directory"]
    assert [(x["brand"], [w["name"] for w in x["workspaces"]]) for x in d] == [("Acme", ["Team"])]


def test_data_survives_a_restart(tmp_path):
    a = TeamStore(tmp_path / "x.db")
    token, me = a.sign_up("Kate", "k@x.com", PW, "Content Creator", None)
    b = TeamStore(tmp_path / "x.db")
    assert b.account_for(token)["id"] == me["id"]
    assert b.sign_in("k@x.com", PW)[1]["id"] == me["id"]


# ------------------------------------------------------------- Supabase Auth mirror

import httpx  # noqa: E402

from engano_backend.auth_mirror import AuthMirror  # noqa: E402


def _mirror(handler):
    return AuthMirror("https://p.supabase.co", "secret", httpx.Client(transport=httpx.MockTransport(handler)))


def test_mirror_does_nothing_without_a_secret_key():
    assert AuthMirror("https://p.supabase.co", None).push({"id": "u", "email": "a@x.com", "name": "A", "purpose": "Reviewer"}) is None


def test_mirror_creates_a_confirmed_user_with_the_admin_api():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers["authorization"]
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "sb-1"})

    out = _mirror(handler).push({"id": "u_1", "email": "a@x.com", "name": "A", "purpose": "Business", "brand": "Acme"}, "pw-12345")
    assert out == "sb-1"
    assert seen["url"] == "https://p.supabase.co/auth/v1/admin/users" and seen["auth"] == "Bearer secret"
    assert seen["body"]["email_confirm"] is True and seen["body"]["password"] == "pw-12345"
    assert seen["body"]["user_metadata"]["purpose"] == "Business"


def test_a_refusing_or_unreachable_mirror_never_breaks_sign_up(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    def boom(request):
        raise httpx.ConnectError("down")

    for n, handler in enumerate((lambda r: httpx.Response(500), boom)):
        c = make_client(tmp_path, f"m{n}.db", auth_mirror=_mirror(handler))
        r = c.post("/api/auth/signup", json={"name": "Kate", "email": "k@x.com", "password": PW, "purpose": "Content Creator"})
        assert r.status_code == 200
        assert c.post("/api/auth/signin", json={"email": "k@x.com", "password": PW}).status_code == 200


def test_signups_and_reviewers_are_mirrored_and_backfill_lists_the_rest(tmp_path):
    created = []

    def handler(request):
        created.append(__import__("json").loads(request.content)["email"])
        return httpx.Response(200, json={"id": f"sb-{len(created)}"})

    store = TeamStore(tmp_path / "b.db")
    store.sign_up("Old", "old@x.com", PW, "Content Creator", None)  # signed up before the key existed
    assert [a["email"] for a in store.accounts_to_mirror()] == ["old@x.com"]
    mirror = _mirror(handler)
    for account in store.accounts_to_mirror():
        store.set_supabase_id(account["id"], mirror.push(account))
    assert store.accounts_to_mirror() == [] and created == ["old@x.com"]


# ------------------------------------------------------- reviewer contact + messages

import asyncio  # noqa: E402

from engano_backend.notify import ReviewerNotifier, normalize_discord, normalize_whatsapp  # noqa: E402
from engano_whatsapp.client import WhatsAppClient  # noqa: E402


class FakeNotifier:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def send(self, contact, text):
        if self.fail:
            raise RuntimeError("boom")
        self.sent.append((contact, text))
        return {p: "sent" for p, v in (("WhatsApp", contact.get("whatsapp")), ("Discord", contact.get("discord_id"))) if v}


def team_with(tmp_path, notifier):
    c = make_client(tmp_path, f"n{id(notifier)}.db", notifier=notifier)
    boss = sign_up(c, "Boss", "Business", "Acme")
    ws = c.post("/api/app/workspaces", json={"name": "Team"}, headers=boss).json()["id"]
    made = c.post(f"/api/app/workspaces/{ws}/reviewers", json={"name": "Rita", "email": "rita@x.com"}, headers=boss).json()
    rita = {"Authorization": "Bearer " + c.post("/api/auth/signin", json={"email": "rita@x.com", "password": made["password"]}).json()["token"]}
    code = c.get("/api/app/state", headers=boss).json()["workspaces"][0]["code"]
    kate = sign_up(c, "Kate", "Content Creator")
    c.post("/api/app/join", json={"code": code}, headers=kate)
    return c, boss, rita, kate


def test_phone_and_discord_normalisation():
    assert normalize_whatsapp("+91 98765-43210") == "919876543210"
    assert normalize_whatsapp("9876543210") == "919876543210"
    assert normalize_whatsapp("12") is None and normalize_whatsapp("") is None
    assert normalize_discord("123456789012345678") == "123456789012345678"
    assert normalize_discord("not-an-id") is None and normalize_discord("1234") is None


def test_reviewer_saves_and_clears_contact(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    c, boss, rita, kate = team_with(tmp_path, FakeNotifier())
    r = c.put("/api/app/me/contact", json={"whatsapp": "+91 98765 43210", "discord_id": "123456789012345678"}, headers=rita)
    assert r.status_code == 200 and r.json()["whatsapp"] == "919876543210" and r.json()["discordId"] == "123456789012345678"
    assert c.get("/api/app/state", headers=rita).json()["me"]["whatsapp"] == "919876543210"
    assert c.put("/api/app/me/contact", json={"whatsapp": "12"}, headers=rita).status_code == 400
    assert c.put("/api/app/me/contact", json={"discord_id": "abc"}, headers=rita).status_code == 400
    cleared = c.put("/api/app/me/contact", json={}, headers=rita).json()
    assert cleared["whatsapp"] == "" and cleared["discordId"] == ""
    for who in (kate, boss):
        assert c.put("/api/app/me/contact", json={"whatsapp": "919876543210"}, headers=who).status_code == 403


def test_pending_drafts_are_sent_to_reviewers_who_saved_a_contact(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    fake = FakeNotifier()
    c, boss, rita, kate = team_with(tmp_path, fake)
    c.post("/api/app/submissions", json={"title": "Launch", "content": BAD}, headers=kate)
    assert fake.sent == []  # no contact saved yet
    c.put("/api/app/me/contact", json={"discord_id": "123456789012345678"}, headers=rita)
    c.post(
        "/api/app/submissions",
        json={"title": "Launch 2", "content": BAD, "ai_status": "RED", "findings": [{"issue": "“100% uptime”", "severity": "Critical", "explanation": "Contradicts the SLA."}]},
        headers=kate,
    )
    assert len(fake.sent) == 1
    contact, text = fake.sent[0]
    assert contact["discord_id"] == "123456789012345678" and contact["whatsapp"] is None
    for part in ("waiting for your review", "Workspace: Team", "From: Kate", "Launch 2", BAD, "100% uptime", "Contradicts the SLA."):
        assert part in text, part


def test_ai_cleared_drafts_are_not_sent_to_reviewers(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    fake = FakeNotifier()
    c, boss, rita, kate = team_with(tmp_path, fake)
    c.put("/api/app/me/contact", json={"whatsapp": "919876543210"}, headers=rita)
    receipt, _ = review(c, CLEAN, kate)
    sub = c.post("/api/app/submissions", json={"title": "ok", "content": CLEAN, "receipt": receipt}, headers=kate).json()
    assert sub["status"] == "Approved" and fake.sent == []


def test_a_failing_notifier_never_breaks_submitting(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    c, boss, rita, kate = team_with(tmp_path, FakeNotifier(fail=True))
    c.put("/api/app/me/contact", json={"whatsapp": "919876543210"}, headers=rita)
    r = c.post("/api/app/submissions", json={"title": "x", "content": BAD}, headers=kate)
    assert r.status_code == 200 and r.json()["status"] == "Pending Review"


def test_test_message_reports_each_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    fake = FakeNotifier()
    c, boss, rita, kate = team_with(tmp_path, fake)
    assert c.post("/api/app/me/contact/test", headers=rita).status_code == 400
    c.put("/api/app/me/contact", json={"whatsapp": "919876543210", "discord_id": "123456789012345678"}, headers=rita)
    assert c.post("/api/app/me/contact/test", headers=rita).json() == {"WhatsApp": "sent", "Discord": "sent"}


def _http(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_notifier_sends_whatsapp_and_discord_dm(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "555")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.content.decode()))
        if request.url.path.endswith("/users/@me/channels"):
            return httpx.Response(200, json={"id": "dm1"})
        return httpx.Response(200, json={})

    http = _http(handler)
    n = ReviewerNotifier(WhatsAppClient("tok", "v25.0", http), "bot-token", http=http)
    out = asyncio.run(n.send({"whatsapp": "919876543210", "discord_id": "123456789012345678"}, "hello"))
    assert out == {"WhatsApp": "sent", "Discord": "sent"}
    urls = [u for _, u, _ in calls]
    assert any(u.endswith("/555/messages") for u in urls)
    assert any(u.endswith("/users/@me/channels") for u in urls) and any(u.endswith("/channels/dm1/messages") for u in urls)
    assert '"to":"919876543210"' in next(b for _, u, b in calls if u.endswith("/555/messages")).replace(" ", "")


def test_notifier_reports_why_delivery_failed(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "555")
    http = _http(lambda r: httpx.Response(403, text="nope"))
    n = ReviewerNotifier(WhatsAppClient("tok", "v25.0", http), "bot-token", http=http)
    out = asyncio.run(n.send({"whatsapp": "919876543210", "discord_id": "123456789012345678"}, "hi"))
    assert "HTTP 403" in out["WhatsApp"] and "share a server" in out["Discord"]
    unset = ReviewerNotifier(None, None, http=http)
    assert "not set up" in asyncio.run(unset.send({"whatsapp": "919876543210"}, "x"))["WhatsApp"]


# ------------------------------------------------ workspace rules decide, not just display

def set_rules(c, boss, ws, *rules):
    items = [{"type": t, "text": x} for t, x in rules]
    assert c.put(f"/api/app/workspaces/{ws}/guidelines", json={"items": items}, headers=boss).status_code == 200


def test_a_banned_word_in_a_creators_review_is_found_and_never_clears(client):
    boss, _, kate, ws = team(client)
    set_rules(client, boss, ws, ("DON'T", "Never use the word cheap."))
    text = "Nimbus DB is a cheap platform for modern teams."
    receipt, body = review(client, text, kate)
    found = [f for f in body["findings"] if f["category"] == "brand_guideline"]
    assert found and found[0]["highlighted_text"] == "cheap" and body["decision"]["status"] == "RED"
    sub = client.post("/api/app/submissions", json={"title": "t", "content": text, "receipt": receipt}, headers=kate).json()
    assert sub["status"] == "Pending Review"


def test_a_rule_nobody_can_check_still_sends_the_draft_to_a_person(client):
    boss, _, kate, ws = team(client)
    set_rules(client, boss, ws, ("DO", "Ojas is a fitness company"))
    receipt, body = review(client, CLEAN, kate)
    assert any(f["category"] == "brand_guideline" and f["human_review_required"] for f in body["findings"])
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN, "receipt": receipt}, headers=kate).json()
    assert sub["status"] == "Pending Review"


def test_only_a_review_done_with_the_workspace_rules_can_clear_a_draft(client):
    boss, _, kate, ws = team(client)
    set_rules(client, boss, ws, ("DON'T", "Never use the word cheap."))
    anonymous, _ = review(client, CLEAN)  # reviewed with no sign-in, so without the workspace's rules
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN, "receipt": anonymous}, headers=kate).json()
    assert sub["status"] == "Pending Review"
    proper, _ = review(client, CLEAN, kate)  # a followed word ban leaves nothing to check
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN, "receipt": proper}, headers=kate).json()
    assert (sub["status"], sub["approvedBy"]) == ("Approved", "AI")


def test_changing_the_rules_after_a_review_voids_its_receipt(client):
    boss, _, kate, ws = team(client)
    receipt, _ = review(client, CLEAN, kate)
    set_rules(client, boss, ws, ("DON'T", "Never use the word reliable."))
    sub = client.post("/api/app/submissions", json={"title": "t", "content": CLEAN, "receipt": receipt}, headers=kate).json()
    assert sub["status"] == "Pending Review"


def test_a_client_cannot_supply_its_own_rules_or_scope(client):
    boss, _, kate, ws = team(client)
    set_rules(client, boss, ws, ("DON'T", "Never use the word cheap."))
    r = client.post("/api/review", json={"text": "cheap", "workspace_rules": [], "scope": "x"}, headers=kate)
    assert r.status_code == 200
    assert any(f["category"] == "brand_guideline" for f in r.json()["findings"])


# ----------------------------------------------------- revision history and comments

def detail(c, who, sid):
    r = c.get(f"/api/app/submissions/{sid}", headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def test_every_version_and_event_is_kept(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "Launch", "content": BAD, "ai_status": "RED"}, headers=kate).json()["id"]
    d = detail(client, kate, sid)
    assert [v["version"] for v in d["versions"]] == [1] and d["versions"][0]["content"] == BAD
    assert [e["kind"] for e in d["events"]] == ["submitted"] and d["events"][0]["by"] == "Kate"
    client.post(f"/api/app/submissions/{sid}/reject", json={"comment": "Remove the uptime claim."}, headers=rita)
    receipt, _ = review(client, CLEAN, kate)
    client.post("/api/app/submissions", json={"title": "Launch", "content": CLEAN, "receipt": receipt, "editing_id": sid}, headers=kate)
    d = detail(client, boss, sid)
    assert [v["version"] for v in d["versions"]] == [1, 2]
    assert [v["content"] for v in d["versions"]] == [BAD, CLEAN]
    assert [e["kind"] for e in d["events"]] == ["submitted", "rejected", "resubmitted", "cleared"]
    rejected = d["events"][1]
    assert (rejected["by"], rejected["body"], rejected["version"]) == ("Rita", "Remove the uptime claim.", 1)
    assert d["events"][3]["by"] == "ENGANO"
    assert d["submission"]["version"] == 2 and d["submission"]["status"] == "Approved"


def test_approval_is_in_the_timeline_and_the_snapshot_counts_versions_and_comments(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    client.post(f"/api/app/submissions/{sid}/approve", headers=rita)
    assert [e["kind"] for e in detail(client, rita, sid)["events"]] == ["submitted", "approved"]
    client.post(f"/api/app/submissions/{sid}/comments", json={"body": "Looks fine now."}, headers=boss)
    row = client.get("/api/app/state", headers=kate).json()["submissions"][0]
    assert (row["version"], row["comments"]) == (1, 1)


def test_creator_reviewer_and_manager_can_comment_and_see_the_thread(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    for who, text in ((kate, "Question: is 99.95 right?"), (rita, "Yes, use the SLA wording."), (boss, "Agreed.")):
        assert client.post(f"/api/app/submissions/{sid}/comments", json={"body": text}, headers=who).status_code == 200
    for who in (kate, rita, boss):
        thread = [(e["by"], e["body"]) for e in detail(client, who, sid)["events"] if e["kind"] == "comment"]
        assert thread == [("Kate", "Question: is 99.95 right?"), ("Rita", "Yes, use the SLA wording."), ("Boss", "Agreed.")]


def test_outsiders_cannot_read_or_comment(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    other_boss = sign_up(client, "Other", "Business", "Other Co")
    other_creator = sign_up(client, "Out", "Content Creator")
    ows = client.post("/api/app/workspaces", json={"name": "Elsewhere"}, headers=other_boss).json()["id"]
    stray = client.post(f"/api/app/workspaces/{ows}/reviewers", json={"name": "Stray", "email": "stray@x.com"}, headers=other_boss).json()
    stray_h = {"Authorization": "Bearer " + client.post("/api/auth/signin", json={"email": "stray@x.com", "password": stray["password"]}).json()["token"]}
    for who in (other_boss, other_creator, stray_h):
        assert client.get(f"/api/app/submissions/{sid}", headers=who).status_code == 404
        assert client.post(f"/api/app/submissions/{sid}/comments", json={"body": "hi"}, headers=who).status_code == 404
    assert client.get(f"/api/app/submissions/{sid}").status_code == 401
    assert client.get("/api/app/submissions/99999", headers=kate).status_code == 404


@pytest.mark.parametrize("body", ["", "   ", "x" * 2001])
def test_comments_must_have_a_sensible_length(client, body):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    assert client.post(f"/api/app/submissions/{sid}/comments", json={"body": body}, headers=kate).status_code in (400, 422)


def test_a_new_comment_shows_up_without_waiting(client):
    boss, rita, kate, _ = team(client)
    sid = client.post("/api/app/submissions", json={"title": "A", "content": BAD}, headers=kate).json()["id"]
    assert detail(client, kate, sid)["events"][-1]["kind"] == "submitted"
    client.post(f"/api/app/submissions/{sid}/comments", json={"body": "ping"}, headers=rita)
    assert detail(client, kate, sid)["events"][-1]["body"] == "ping"  # cached views are dropped by any write


def test_old_drafts_get_a_first_version_and_a_timeline(tmp_path):
    store = new_store(tmp_path, "old.db")
    _, boss = store.sign_up("Boss", "boss@x.com", PW, "Business", "Acme")
    ws = store.create_workspace(boss["id"], "Team")
    _, kate = store.sign_up("Kate", "kate@x.com", PW, "Content Creator", None)
    code = store.snapshot(boss["id"])["workspaces"][0]["code"]
    store.join_by_code(kate["id"], code)
    sub = store.submit(kate["id"], "Old", BAD, [], "RED", None, None)
    with store._tx() as db:  # simulate a draft made before history existed
        db.execute("DELETE FROM submission_events WHERE submission_id = ?", (sub["id"],))
        db.execute("DELETE FROM submission_versions WHERE submission_id = ?", (sub["id"],))
    with store._tx() as db:
        store._backfill_history(db)
    d = store.submission_detail(kate["id"], sub["id"])
    assert [v["version"] for v in d["versions"]] == [1] and [e["kind"] for e in d["events"]] == ["submitted"]
    assert ws  # the workspace exists
