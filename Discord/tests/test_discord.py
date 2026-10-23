"""Discord review tests: real ai_engine + Nimbus fixture, no Discord connection."""

import asyncio

import pytest

from engano_backend.review_service import ReviewService, ReviewSettings
from engano_discord.review import Draft, render_result, to_payload

IMAGE = "https://cdn.discordapp.com/attachments/1/2/flyer.png"


@pytest.fixture
def reviews():
    return ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))


def review(reviews: ReviewService, draft: Draft):
    payload = to_payload(reviews, draft, "discord-test")
    return payload, asyncio.run(reviews.review_payload(payload))


def test_payload_uses_trusted_brand_and_alt_text(reviews):
    draft = Draft("discord", "42", "Hello", image_urls=[IMAGE], image_alt_texts=["Nimbus DB launch flyer"])
    payload = to_payload(reviews, draft, "discord-1")
    assert payload.brand_id == "nimbus_cloud"
    assert payload.channel.value == "discord"
    assert payload.draft_id == "discord-1"
    assert payload.images[0].url == IMAGE
    assert payload.images[0].alt_text == "Nimbus DB launch flyer"


def test_bad_draft_is_red_with_rechecked_rewrite(reviews):
    _, result = review(reviews, Draft("discord", "42", "NimbusDB has 100% uptime."))
    embed = render_result(Draft("discord", "42", "NimbusDB has 100% uptime."), result)
    assert "Needs reviewer approval" in embed.title
    rewrite = next(f.value for f in embed.fields if f.name == "Suggested rewrite")
    assert "99.95%" in rewrite and "Re-checked: the rewrite passes." in rewrite


def test_image_without_alt_text_is_flagged(reviews):
    draft = Draft("discord", "42", "", image_urls=[IMAGE], image_alt_texts=[None])
    _, result = review(reviews, draft)
    assert any(f.category.value == "visual_wcag" for f in result.findings)
    assert any(f.name == "Images" for f in render_result(draft, result).fields)


def test_image_with_alt_text_passes(reviews):
    draft = Draft("discord", "42", "", image_urls=[IMAGE], image_alt_texts=["Nimbus DB launch flyer"])
    _, result = review(reviews, draft)
    assert not any(f.category.value == "visual_wcag" for f in result.findings)
