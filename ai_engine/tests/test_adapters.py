"""Tests for Stage 1 multi-channel adapters."""

import pytest
from ai_engine.adapters import (
    DiscordAdapter,
    GmailAdapter,
    LinkedInAdapter,
    WebStudioAdapter,
    WhatsAppAdapter,
    get_adapter,
)
from ai_engine.schemas.payload import ChannelType, DraftPayload, ImageItem, VisualMetadata


def test_web_studio_adapter():
    adapter = WebStudioAdapter()
    raw = {
        "draft_id": "studio-001",
        "text": "Try our cloud database today.",
        "visual_metadata": {"contrast_ratio": 5.2, "is_large_text": False},
        "images": [{"url": "https://example.com/logo.png", "alt_text": "Logo"}],
    }
    payload = adapter.normalize(raw, brand_id="nimbus_cloud")

    assert isinstance(payload, DraftPayload)
    assert payload.draft_id == "studio-001"
    assert payload.brand_id == "nimbus_cloud"
    assert payload.channel == ChannelType.WEB_STUDIO
    assert payload.content_text == "Try our cloud database today."
    assert payload.visual_metadata is not None
    assert payload.visual_metadata.contrast_ratio == 5.2
    assert len(payload.images) == 1
    assert payload.images[0].alt_text == "Logo"


def test_web_studio_adapter_rejects_none():
    adapter = WebStudioAdapter()
    with pytest.raises(ValueError, match="cannot be None"):
        adapter.normalize(None, brand_id="nimbus_cloud")


def test_discord_adapter_from_dict():
    adapter = DiscordAdapter()
    raw = {
        "message_id": "123456789",
        "content": "Check out Nimbus DB on Discord!",
        "author_id": "user-42",
        "attachments": [{"url": "https://cdn.discordapp.com/banner.png"}],
    }
    payload = adapter.normalize(raw, brand_id="nimbus_cloud")

    assert payload.channel == ChannelType.DISCORD
    assert payload.content_text == "Check out Nimbus DB on Discord!"
    assert len(payload.images) == 1
    assert payload.images[0].url == "https://cdn.discordapp.com/banner.png"
    assert payload.metadata["author_id"] == "user-42"


def test_whatsapp_adapter_with_image_metadata():
    adapter = WhatsAppAdapter()
    raw = {
        "id": "wamid.123",
        "sender": "15551234567",
        "phone_number_id": "biz-888",
        "type": "image",
        "image": {
            "id": "media-01",
            "url": "https://lookaside.fbsbx.com/media-01",
            "caption": "NimbusDB flyer with 100% uptime SLA",
            "mime_type": "image/jpeg",
        },
    }
    payload = adapter.normalize(raw, brand_id="nimbus_cloud")

    assert payload.channel == ChannelType.WHATSAPP
    assert payload.draft_id == "whatsapp-wamid.123"
    assert payload.content_text == "NimbusDB flyer with 100% uptime SLA"
    assert len(payload.images) == 1
    assert payload.images[0].mime_type == "image/jpeg"
    assert payload.images[0].alt_text == "NimbusDB flyer with 100% uptime SLA"
    assert payload.metadata["sender"] == "15551234567"
    assert payload.visual_metadata is not None
    assert payload.visual_metadata.has_alt_text is True


def test_gmail_adapter_with_html_strip():
    adapter = GmailAdapter()
    raw = {
        "message_id": "gmail-msg-99",
        "subject": "Exclusive Launch Offer",
        "body_html": "<p>Nimbus DB is here! <strong>Try it now</strong>.</p>",
        "attachments": [
            {"filename": "promo.png", "mimeType": "image/png", "size": 10240}
        ],
        "from": "marketing@example.com",
    }
    payload = adapter.normalize(raw, brand_id="nimbus_cloud")

    assert payload.channel == ChannelType.GMAIL
    assert payload.draft_id == "gmail-gmail-msg-99"
    assert "Exclusive Launch Offer" in payload.content_text
    assert "Nimbus DB is here! Try it now." in payload.content_text
    assert len(payload.images) == 1
    assert payload.images[0].mime_type == "image/png"
    assert payload.metadata["subject"] == "Exclusive Launch Offer"


def test_linkedin_adapter():
    adapter = LinkedInAdapter()
    raw = {
        "post_urn": "urn:li:share:777888",
        "commentary": "Supercharge your stack with Nimbus DB.",
        "media": [
            {"url": "https://media.licdn.com/banner.jpg", "alt_text": "Cloud Architecture"}
        ],
        "author_urn": "urn:li:person:123",
    }
    payload = adapter.normalize(raw, brand_id="nimbus_cloud")

    assert payload.channel == ChannelType.LINKEDIN
    assert payload.content_text == "Supercharge your stack with Nimbus DB."
    assert len(payload.images) == 1
    assert payload.images[0].alt_text == "Cloud Architecture"
    assert payload.metadata["author_urn"] == "urn:li:person:123"


def test_adapter_factory():
    for ch in ChannelType:
        ad = get_adapter(ch)
        assert ad is not None

    with pytest.raises(ValueError, match="Unsupported channel"):
        get_adapter("unknown_channel")
