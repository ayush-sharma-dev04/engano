"""WhatsApp: images are downloaded and checked, and failures degrade safely."""

import base64
import hashlib
import hmac
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from engano_backend.app import create_app
from engano_backend.escalation import EscalationSettings
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_whatsapp.config import WhatsAppSettings
from engano_whatsapp.payload import parse_messages

SECRET = "s"


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


class Fake:
    def __init__(self, media=None, fail=False):
        self.sent, self.media, self.fail, self.downloads = [], media, fail, []

    async def send_text(self, phone_number_id, to, text, reply_to=None):
        self.sent.append(text)

    async def mark_read(self, *a):
        pass

    async def download_media(self, media_id, max_bytes=0):
        self.downloads.append(media_id)
        if self.fail:
            raise RuntimeError("expired media")
        return self.media

    async def aclose(self):
        pass


def image_message(media_id="MEDIA1"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "W", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "1", "phone_number_id": "P"},
        "messages": [{"from": "919800000000", "id": "wamid.img", "timestamp": "1", "type": "image",
                      "image": {"id": media_id, "caption": "Nimbus DB launch", "mime_type": "image/jpeg"}}]}}]}]}


def post(client, body):
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/whatsapp", content=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})


def make(fake):
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    return TestClient(create_app(reviews, WhatsAppSettings(access_token="t", app_secret=SECRET, verify_token="v"), fake,
                                 escalation=EscalationSettings()))


def test_media_id_is_parsed():
    (msg,) = parse_messages(image_message("ABC"))
    assert msg.media_id == "ABC" and msg.has_image


def test_image_is_downloaded_and_analysed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    fake = Fake(media=png())
    with make(fake) as client:
        post(client, image_message())
    assert fake.downloads == ["MEDIA1"]
    assert "the text in it, its contrast and any logos were checked" in fake.sent[-1]


def test_failed_download_falls_back_to_the_accessibility_check(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    fake = Fake(fail=True)
    with make(fake) as client:
        post(client, image_message())
    assert "couldn't open the image itself" in fake.sent[-1]
