"""WhatsApp webhook tests: real ai_engine + Nimbus fixture, fake WhatsApp API."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_whatsapp.config import WhatsAppSettings
from engano_whatsapp.payload import parse_messages
from engano_whatsapp.signature import verify_signature

SECRET = "test-app-secret"
VERIFY = "test-verify-token"
PHONE_ID = "1234567890"
BAD_DRAFT = "NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever!"


class FakeWhatsApp:
    def __init__(self):
        self.sent: list[dict] = []
        self.read: list[str] = []

    async def send_text(self, phone_number_id, to, text, reply_to=None):
        self.sent.append({"from": phone_number_id, "to": to, "text": text, "reply_to": reply_to})

    async def mark_read(self, phone_number_id, message_id):
        self.read.append(message_id)

    async def aclose(self):
        pass


def message(msg_id: str, **content) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550000000", "phone_number_id": PHONE_ID},
                    "contacts": [{"profile": {"name": "Test"}, "wa_id": "919800000000"}],
                    "messages": [{"from": "919800000000", "id": msg_id, "timestamp": "1761100000", **content}],
                },
            }],
        }],
    }


def text_message(msg_id: str, body: str) -> dict:
    return message(msg_id, type="text", text={"body": body})


def signed_post(client: TestClient, payload: dict, secret: str = SECRET):
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/webhooks/whatsapp",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )


@pytest.fixture
def fake():
    return FakeWhatsApp()


@pytest.fixture
def client(fake):
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    settings = WhatsAppSettings(access_token="token", app_secret=SECRET, verify_token=VERIFY)
    with TestClient(create_app(reviews, settings, fake)) as c:
        yield c


def test_verification_handshake(client):
    ok = client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"})
    assert bad.status_code == 403


def test_rejects_bad_signature(client, fake):
    resp = signed_post(client, text_message("wamid.1", BAD_DRAFT), secret="not-the-secret")
    assert resp.status_code == 401
    assert fake.sent == []


def test_reviews_text_and_replies(client, fake):
    resp = signed_post(client, text_message("wamid.2", BAD_DRAFT))
    assert resp.status_code == 200
    assert fake.read == ["wamid.2"]
    [reply] = fake.sent
    assert reply["to"] == "919800000000" and reply["from"] == PHONE_ID and reply["reply_to"] == "wamid.2"
    text = reply["text"]
    assert "Needs reviewer approval" in text
    assert '"NimbusDB" → "Nimbus DB"' in text
    assert "99.95% uptime SLA" in text
    assert "Suggested rewrite" in text


def test_clean_draft_is_green_without_rewrite(client, fake):
    signed_post(
        client,
        text_message("wamid.3", "Nimbus DB keeps your data safe with a 99.95% uptime SLA. Terms and conditions apply to service SLA."),
    )
    text = fake.sent[0]["text"]
    assert "Ready to publish" in text
    assert "Suggested rewrite" not in text


def test_duplicate_delivery_replies_once(client, fake):
    signed_post(client, text_message("wamid.4", BAD_DRAFT))
    signed_post(client, text_message("wamid.4", BAD_DRAFT))
    assert len(fake.sent) == 1


def test_help_image_and_unsupported(client, fake):
    signed_post(client, text_message("wamid.5", "help"))
    signed_post(client, message("wamid.6", type="image", image={"id": "media1", "mime_type": "image/jpeg"}))
    signed_post(client, message("wamid.7", type="image", image={"id": "media2", "caption": BAD_DRAFT}))
    signed_post(client, message("wamid.8", type="audio", audio={"id": "media3"}))
    help_text, image_only, captioned, unsupported = (m["text"] for m in fake.sent)
    assert "ENGANO brand check" in help_text
    # Image-only drafts now go through the engine (alt text has no source on WhatsApp).
    assert "Accessibility" in image_only and "alternative text" in image_only and "couldn't open the image itself" in image_only
    assert "Needs reviewer approval" in captioned and "couldn't open the image itself" in captioned
    assert "only check text" in unsupported


def test_rewrite_is_rechecked(client, fake):
    signed_post(client, text_message("wamid.10", "NimbusDB has 100% uptime."))
    text = fake.sent[0]["text"]
    assert "Suggested rewrite" in text and "Re-checked: the rewrite passes." in text


def test_status_updates_are_ignored(client, fake):
    payload = text_message("unused", "")
    value = payload["entry"][0]["changes"][0]["value"]
    del value["messages"]
    value["statuses"] = [{"id": "wamid.9", "status": "delivered"}]
    assert signed_post(client, payload).status_code == 200
    assert fake.sent == []


def test_refuses_messages_without_app_secret(fake):
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    settings = WhatsAppSettings(access_token="token", app_secret=None, verify_token=VERIFY)
    with TestClient(create_app(reviews, settings, fake)) as c:
        assert signed_post(c, text_message("wamid.10", BAD_DRAFT)).status_code == 503


def test_signature_helper():
    raw = b'{"a":1}'
    good = "sha256=" + hmac.new(b"s", raw, hashlib.sha256).hexdigest()
    assert verify_signature(raw, good, "s")
    assert not verify_signature(raw, good, "other")
    assert not verify_signature(raw, None, "s")


def test_parse_ignores_other_objects():
    assert parse_messages({"object": "page", "entry": []}) == []
