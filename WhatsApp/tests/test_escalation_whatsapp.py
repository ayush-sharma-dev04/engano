"""WhatsApp: unsure drafts are forwarded to the human reviewer."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from engano_backend.app import create_app
from engano_backend.escalation import EscalationSettings
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_whatsapp.config import WhatsAppSettings

SECRET = "s"
REVIEWER = "919876500001"
BAD = "NimbusDB has 100% uptime. Try it free forever!"
CLEAN = "Nimbus DB is a reliable platform for modern teams."


class Fake:
    def __init__(self, fail_for: str | None = None):
        self.sent, self.fail_for = [], fail_for

    async def send_text(self, phone_number_id, to, text, reply_to=None):
        if to == self.fail_for:
            raise RuntimeError("recipient not allowed")
        self.sent.append({"to": to, "text": text})

    async def mark_read(self, *a):
        pass

    async def aclose(self):
        pass


def post(client, body, sender="919800000000", msg_id="m1"):
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "W", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "1", "phone_number_id": "P"},
        "messages": [{"from": sender, "id": msg_id, "timestamp": "1", "type": "text", "text": {"body": body}}]}}]}]}
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/whatsapp", content=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})


def make(fake, reviewer=REVIEWER):
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    return TestClient(create_app(
        reviews, WhatsAppSettings(access_token="t", app_secret=SECRET, verify_token="v"), fake,
        escalation=EscalationSettings(whatsapp_number=reviewer),
    ))


def test_unsure_draft_goes_to_reviewer_and_sender_is_told():
    fake = Fake()
    with make(fake) as client:
        post(client, BAD)
    to_reviewer = [m for m in fake.sent if m["to"] == REVIEWER]
    to_sender = [m for m in fake.sent if m["to"] == "919800000000"]
    assert len(to_reviewer) == 1 and BAD in to_reviewer[0]["text"] and "+919800000000" in to_reviewer[0]["text"]
    assert "Sent to a reviewer" in to_sender[0]["text"]


def test_clean_draft_is_not_forwarded():
    fake = Fake()
    with make(fake) as client:
        post(client, CLEAN + " Terms and conditions apply to service SLA.")
    assert all(m["to"] != REVIEWER for m in fake.sent)
    assert all("Sent to a reviewer" not in m["text"] for m in fake.sent)


def test_unreachable_reviewer_is_reported_honestly():
    fake = Fake(fail_for=REVIEWER)
    with make(fake) as client:
        post(client, BAD)
    reply = fake.sent[-1]
    assert reply["to"] == "919800000000" and "couldn't reach the reviewer" in reply["text"]


def test_reviewer_own_drafts_are_not_echoed_back_to_them():
    fake = Fake()
    with make(fake) as client:
        post(client, BAD, sender=REVIEWER)
    assert len([m for m in fake.sent if m["to"] == REVIEWER]) == 1  # only their own reply


def test_no_reviewer_configured_changes_nothing():
    fake = Fake()
    with make(fake, reviewer=None) as client:
        post(client, BAD)
    assert len(fake.sent) == 1 and "Sent to a reviewer" not in fake.sent[0]["text"]
