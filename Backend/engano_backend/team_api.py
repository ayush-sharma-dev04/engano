"""HTTP routes for accounts, workspaces and the review pipeline (see team_store)."""

import time
from collections import defaultdict, deque
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .auth_mirror import AuthMirror
from .notify import ReviewerNotifier, normalize_discord, normalize_whatsapp, review_request_text
from .team_store import Refused, TeamStore

log = logging.getLogger("engano.team")
MAX_FAILURES = 8
FAILURE_WINDOW = 300.0


class SignUp(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=160)
    password: str = Field(max_length=200)
    purpose: str = Field(max_length=30)
    brand: str | None = Field(default=None, max_length=80)


class SignIn(BaseModel):
    email: str = Field(max_length=160)
    password: str = Field(max_length=200)


class Named(BaseModel):
    name: str = Field(max_length=120)


class Code(BaseModel):
    code: str = Field(max_length=20)


class Answer(BaseModel):
    accept: bool


class NewReviewer(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=160)


class ReviewerRef(BaseModel):
    reviewer_id: str = Field(max_length=40)


class AssignmentIn(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=5000)
    due_date: str = Field(max_length=10)


class GuidelinesIn(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=200)


class SubmitIn(BaseModel):
    title: str = Field(default="", max_length=200)
    content: str = Field(max_length=10_000)
    findings: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    ai_status: str | None = Field(default=None, max_length=10)
    receipt: str | None = Field(default=None, max_length=100)
    editing_id: int | None = None


class ContactIn(BaseModel):
    whatsapp: str = Field(default="", max_length=40)
    discord_id: str = Field(default="", max_length=40)


class Reject(BaseModel):
    comment: str = Field(max_length=2000)


def build_router(store: TeamStore, mirror: AuthMirror | None = None, notifier: ReviewerNotifier | None = None) -> APIRouter:
    mirror = mirror or AuthMirror(None, None)
    notifier = notifier or ReviewerNotifier(None, None)
    router = APIRouter(prefix="/api")
    failures: dict[str, deque] = defaultdict(deque)

    def fail(error: Refused) -> HTTPException:
        return HTTPException(status_code=error.status, detail=error.message)

    def token_of(authorization: str | None) -> str | None:
        if authorization and authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return None

    def current(authorization: str | None = Header(default=None)) -> dict:
        me = store.account_for(token_of(authorization))
        if not me:
            raise HTTPException(status_code=401, detail="Please sign in again.")
        return me

    def run(fn, *args):
        try:
            return fn(*args)
        except Refused as error:
            raise fail(error) from None

    def throttled(key: str) -> bool:
        now = time.time()
        q = failures[key]
        while q and now - q[0] > FAILURE_WINDOW:
            q.popleft()
        return len(q) >= MAX_FAILURES

    # ------------------------------------------------------------------ auth

    @router.post("/auth/signup")
    def sign_up(body: SignUp):
        token, me = run(store.sign_up, body.name, body.email, body.password, body.purpose, body.brand)
        mirrored = mirror.push(me, body.password)
        if mirrored:
            store.set_supabase_id(me["id"], mirrored)
        return {"token": token, "me": me}

    @router.post("/auth/signin")
    def sign_in(body: SignIn, request: Request):
        key = f"{(request.client.host if request.client else '?')}|{body.email.strip().lower()}"
        if throttled(key):
            raise HTTPException(status_code=429, detail="Too many wrong attempts. Wait a few minutes and try again.")
        try:
            token, me = store.sign_in(body.email, body.password)
        except Refused as error:
            failures[key].append(time.time())
            raise fail(error) from None
        failures.pop(key, None)
        return {"token": token, "me": me}

    @router.post("/auth/signout")
    def sign_out(authorization: str | None = Header(default=None)):
        token = token_of(authorization)
        if token:
            store.sign_out(token)
        return {"ok": True}

    # ----------------------------------------------------------------- state

    @router.get("/app/state")
    def state(me: dict = Depends(current)):
        return store.snapshot(me["id"])

    # ------------------------------------------------------------ workspaces

    @router.post("/app/workspaces")
    def create_workspace(body: Named, me: dict = Depends(current)):
        return {"id": run(store.create_workspace, me["id"], body.name)}

    @router.delete("/app/workspaces/{workspace_id}")
    def delete_workspace(workspace_id: int, me: dict = Depends(current)):
        run(store.delete_workspace, me["id"], workspace_id)
        return {"ok": True}

    @router.post("/app/join")
    def join(body: Code, me: dict = Depends(current)):
        run(store.join_by_code, me["id"], body.code)
        return {"ok": True}

    @router.post("/app/workspaces/{workspace_id}/request")
    def request_join(workspace_id: int, me: dict = Depends(current)):
        run(store.request_join, me["id"], workspace_id)
        return {"ok": True}

    @router.delete("/app/request")
    def cancel_request(me: dict = Depends(current)):
        store.cancel_request(me["id"])
        return {"ok": True}

    @router.post("/app/workspaces/{workspace_id}/requests/{request_id}")
    def answer(workspace_id: int, request_id: int, body: Answer, me: dict = Depends(current)):
        run(store.answer_request, me["id"], workspace_id, request_id, body.accept)
        return {"ok": True}

    @router.post("/app/leave")
    def leave(me: dict = Depends(current)):
        run(store.leave, me["id"])
        return {"ok": True}

    @router.delete("/app/workspaces/{workspace_id}/members/{member_id}")
    def remove_member(workspace_id: int, member_id: int, me: dict = Depends(current)):
        run(store.remove_member, me["id"], workspace_id, member_id)
        return {"ok": True}

    @router.post("/app/workspaces/{workspace_id}/reviewers")
    def create_reviewer(workspace_id: int, body: NewReviewer, me: dict = Depends(current)):
        made = run(store.create_reviewer, me["id"], workspace_id, body.name, body.email)
        mirrored = mirror.push({"id": made["id"], "email": made["email"], "name": body.name.strip(), "purpose": "Reviewer"}, made["password"])
        if mirrored:
            store.set_supabase_id(made["id"], mirrored)
        return made

    @router.post("/app/workspaces/{workspace_id}/reviewers/existing")
    def add_reviewer(workspace_id: int, body: ReviewerRef, me: dict = Depends(current)):
        run(store.add_reviewer, me["id"], workspace_id, body.reviewer_id)
        return {"ok": True}

    # ------------------------------------------------ assignments, guidelines

    @router.post("/app/workspaces/{workspace_id}/assignments")
    def add_assignment(workspace_id: int, body: AssignmentIn, me: dict = Depends(current)):
        run(store.add_assignment, me["id"], workspace_id, body.title, body.description, body.due_date)
        return {"ok": True}

    @router.put("/app/assignments/{assignment_id}")
    def update_assignment(assignment_id: int, body: AssignmentIn, me: dict = Depends(current)):
        run(store.update_assignment, me["id"], assignment_id, body.title, body.description, body.due_date)
        return {"ok": True}

    @router.delete("/app/assignments/{assignment_id}")
    def delete_assignment(assignment_id: int, me: dict = Depends(current)):
        store.delete_assignment(me["id"], assignment_id)
        return {"ok": True}

    @router.put("/app/workspaces/{workspace_id}/guidelines")
    def set_guidelines(workspace_id: int, body: GuidelinesIn, me: dict = Depends(current)):
        run(store.set_guidelines, me["id"], workspace_id, body.items)
        return {"ok": True}

    # ----------------------------------------------------------- submissions

    async def tell_reviewers(workspace_id: int, creator: str, submission: dict) -> None:
        try:
            text = review_request_text(store.workspace_name(workspace_id), creator, submission)
            for reviewer in store.reviewer_contacts(workspace_id):
                await notifier.send(reviewer, text)
        except Exception:
            log.exception("Could not message the reviewers of workspace %s", workspace_id)

    @router.post("/app/submissions")
    def submit(body: SubmitIn, background: BackgroundTasks, me: dict = Depends(current)):
        saved = run(
            store.submit, me["id"], body.title, body.content, body.findings, body.ai_status, body.receipt, body.editing_id
        )
        # Only drafts that need a person are sent to reviewers; ones ENGANO cleared are not.
        if saved["status"] == "Pending Review":
            background.add_task(tell_reviewers, saved["workspaceId"], me["name"], saved)
        return saved

    @router.put("/app/me/contact")
    def save_contact(body: ContactIn, me: dict = Depends(current)):
        whatsapp = normalize_whatsapp(body.whatsapp) if body.whatsapp.strip() else None
        discord = normalize_discord(body.discord_id) if body.discord_id.strip() else None
        if body.whatsapp.strip() and not whatsapp:
            raise HTTPException(status_code=400, detail="Enter the WhatsApp number with its country code, for example 919876543210.")
        if body.discord_id.strip() and not discord:
            raise HTTPException(status_code=400, detail="A Discord user ID is 17 to 19 digits. Turn on Developer Mode, then right-click your name and choose Copy User ID.")
        return run(store.set_contact, me["id"], whatsapp, discord)

    @router.post("/app/me/contact/test")
    async def test_contact(me: dict = Depends(current)):
        contact = store.contact_of(me["id"])
        if not (contact["whatsapp"] or contact["discord_id"]):
            raise HTTPException(status_code=400, detail="Save a WhatsApp number or Discord ID first.")
        return await notifier.send(contact, "ENGANO: this is a test. You will get review requests here.")

    @router.post("/app/submissions/{submission_id}/approve")
    def approve(submission_id: int, me: dict = Depends(current)):
        run(store.decide, me["id"], submission_id, True, "")
        return {"ok": True}

    @router.post("/app/submissions/{submission_id}/reject")
    def reject(submission_id: int, body: Reject, me: dict = Depends(current)):
        run(store.decide, me["id"], submission_id, False, body.comment)
        return {"ok": True}

    return router
