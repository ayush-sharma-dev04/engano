"""Checking a website: rendered facts and screenshots go through the same review engine."""

import base64
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from starlette.testclient import TestClient

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.memory.store import FileBrandMemoryStore
from ai_engine.providers.base import BaseProvider, ProviderResponse
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.payload import DraftPayload, ImageItem
from engano_backend.app import create_app
from engano_backend.review_service import ReviewService, ReviewSettings
from engano_backend.site_render import RenderedSite
from engano_backend.website import SiteError

CLEAN_FACTS = {
    "title": "Nimbus DB", "lang": "en", "description": "A database", "h1": 1, "images": 2, "imagesMissingAlt": 0,
    "missingAltExamples": [], "autoplayWithSound": 0, "autoplayMovingNoControls": 0, "animatedElements": 0,
    "transitionElements": 0, "reducedMotionSupport": False, "legacyMotion": 0, "fonts": {"Inter": 20}, "viewportMeta": True,
    "contrastChecked": 40, "contrastFails": 0, "contrastExamples": [], "unlabelledFields": 0, "unnamedButtons": 0,
    "unnamedLinks": 0, "vagueLinks": 0, "headingSkips": 0, "tinyText": 0, "insecure": False, "zoomBlocked": False,
    "iframesNoTitle": 0, "smallTargets": 0, "hasMain": True,
    "httpStatus": 200, "blocked": "", "loginWall": False, "nearlyEmpty": False, "brokenLinkCount": 0, "linksChecked": 12,
    "brokenImages": 0, "pageErrors": 0, "consoleErrors": 0, "badResponses": 0, "mobileChecked": True, "mobileOverflowPx": 0,
    "scrolledScreens": 5, "reachedBottom": True, "backAtTop": True,
}


def png_b64(color=(255, 255, 255), text=None) -> str:
    img = Image.new("RGB", (1280, 800), color)
    if text:
        ImageDraw.Draw(img).text((60, 60), text, fill="black", font=ImageFont.load_default(size=56))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def repo():
    r = MockPolicyRepository()
    r.load_fixture("data/brand_library/nimbus_db.json")
    return r


def check(repo, facts, screenshot=None, text="Nimbus DB is a reliable platform."):
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=RulesOnlyProvider(), retriever=None)
    images = [ImageItem(alt_text="Screenshot", metadata={"base64": screenshot or png_b64()})]
    payload = DraftPayload(draft_id="s", brand_id="nimbus_cloud", content_text=text, images=images,
                           metadata={"website_facts": {**CLEAN_FACTS, **facts}, "site_url": "https://acme.example/"},
                           answers={"website": "https://acme.example/"})
    return agent.run_review(payload)


def titles(result):
    return [f.highlighted_text for f in result.findings if f.highlighted_text.startswith("[Website]")]


def test_a_clean_site_has_no_website_findings(repo):
    assert titles(check(repo, {})) == []


@pytest.mark.parametrize("facts,expected", [
    ({"imagesMissingAlt": 3, "missingAltExamples": ["https://a/x.png"]}, "Images without alt text"),
    ({"autoplayWithSound": 1}, "Autoplay with sound"),
    ({"autoplayMovingNoControls": 2}, "Moving video without controls"),
    ({"legacyMotion": 1}, "Blinking or scrolling text"),
    ({"animatedElements": 7}, "Animations ignore reduced-motion setting"),
    ({"title": ""}, "Missing page title"),
    ({"h1": 0}, "No main heading"),
    ({"lang": ""}, "Missing page language"),
    ({"viewportMeta": False}, "Not set up for mobile"),
    ({"insecure": True}, "Not served over HTTPS"),
    ({"contrastFails": 2, "contrastExamples": [{"text": "Buy", "ratio": 2.1, "fg": "#AAAAAA", "bg": "#FFFFFF"}]}, "Low text contrast"),
    ({"unlabelledFields": 1}, "Form fields without labels"),
    ({"unnamedButtons": 1}, "Buttons or links with no name"),
    ({"unnamedLinks": 2}, "Buttons or links with no name"),
    ({"vagueLinks": 3}, "Vague link text"),
    ({"headingSkips": 1}, "Heading levels skipped"),
    ({"iframesNoTitle": 1}, "Embedded frames without a title"),
    ({"zoomBlocked": True}, "Zooming is blocked"),
    ({"tinyText": 3}, "Text smaller than 12px"),
    ({"smallTargets": 1}, "Buttons too small to tap"),
    ({"h1": 2}, "More than one main heading"),
    ({"hasMain": False}, "No main landmark"),
    ({"description": ""}, "No page description"),
    ({"stillLoading": True, "settleSeconds": 25}, "Still on a loading screen"),
    ({"settleSeconds": 7}, "Slow to show content"),
    ({"httpStatus": 503}, "Page returns an error"),
    ({"blocked": "just a moment"}, "Site blocks ENGANO's checker"),
    ({"loginWall": True}, "Page needs a login"),
    ({"nearlyEmpty": True}, "Page is almost empty"),
    ({"brokenLinkCount": 2, "brokenLinks": ["404 https://a/x", "0 https://b/y"]}, "Broken links"),
    ({"brokenImages": 1, "brokenImageExamples": ["https://a/x.png"]}, "Images that fail to load"),
    ({"pageErrors": 1, "pageErrorExamples": ["TypeError: x is undefined"]}, "Errors in the page's code"),
    ({"badResponses": 3, "consoleErrors": 3, "badResponseExamples": ["404 https://a/app.js"]}, "Resources fail to load"),
    ({"mobileOverflowPx": 120}, "Layout breaks on phones"),
    ({"backAtTop": False}, "Page does not scroll back to the top"),
])
def test_each_measured_problem_becomes_a_finding(repo, facts, expected):
    assert f"[Website] {expected}" in titles(check(repo, facts))


def test_animations_are_fine_when_reduced_motion_is_respected(repo):
    assert titles(check(repo, {"animatedElements": 7, "reducedMotionSupport": True})) == []


def test_fonts_are_only_checked_when_the_brand_has_fonts(repo):
    facts = {"fonts": {"Comic Neue": 12, "Inter": 30, "Georgia": 9, "sans-serif": 40}}
    assert titles(check(repo, facts)) == []
    repo.get_policy("nimbus_cloud").visual_style.fonts.append("Inter")
    result = check(repo, facts)
    f = next(f for f in result.findings if f.highlighted_text == "[Website] Fonts outside the brand")
    # Strict: a named font that is not a brand font counts, even a common one. Only CSS keywords are exempt.
    assert "Comic Neue" in f.explanation and "Georgia" in f.explanation
    assert "Inter (" not in f.explanation and "sans-serif (" not in f.explanation


def test_colours_outside_the_palette_are_flagged_only_with_a_palette(repo):
    orange = png_b64(color=(240, 120, 20))
    assert titles(check(repo, {}, screenshot=orange)) == []
    repo.get_policy("nimbus_cloud").visual_style.colors.extend(["#1E3CC8"])
    assert "[Website] Colours outside the brand palette" in titles(check(repo, {}, screenshot=orange))
    assert "[Website] Colours outside the brand palette" not in titles(check(repo, {}, screenshot=png_b64(color=(30, 60, 200))))
    assert "[Website] Colours outside the brand palette" not in titles(check(repo, {}, screenshot=png_b64()))  # white is not a brand colour


def test_the_websites_own_text_is_checked_against_the_brand_rules(repo):
    result = check(repo, {}, text="NimbusDB has 100% uptime. Try it free forever.")
    assert {"terminology", "wrong_fact", "outdated_offer"} <= {f.category.value for f in result.findings}
    assert result.decision.status.value == "RED"


# ------------------------------------------------------------------ API


class Designer(BaseProvider):
    provider_name = "designer"

    def review(self, content_text, policy, deterministic_findings, images=None, context=None):
        return ProviderResponse(provider_name="designer")

    def suggest_visual_changes(self, image_b64, width, height):
        return ["Make the hero heading larger.", "Reduce the number of competing colours."]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "rules_only")
    repo = MockPolicyRepository()
    repo.load_fixture("data/brand_library/nimbus_db.json")
    service = ReviewService(
        ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"),
        repository=repo, memory_store=FileBrandMemoryStore(storage_dir=tmp_path),
    )
    return TestClient(create_app(review_service=service, engine_config=EngineConfig()))


def fake_site(**over):
    base = dict(final_url="https://acme.example/", title="Acme", text="Nimbus DB is great.",
                screenshots=[base64.b64decode(png_b64())], facts={**CLEAN_FACTS, "imagesMissingAlt": 2})
    base.update(over)
    return RenderedSite(**base)


def test_endpoint_returns_screenshot_findings_and_design_notes(client, monkeypatch):
    async def fake_render(url):
        assert url == "acme.example"
        return fake_site()

    monkeypatch.setattr("engano_backend.review_service.render_site", fake_render)
    monkeypatch.setattr("ai_engine.providers.factory.get_provider", lambda config=None: Designer())
    body = client.post("/api/check-website", json={"url": "acme.example"}).json()
    assert body["url"] == "https://acme.example/" and body["screenshot"].startswith("data:image/jpeg;base64,")
    assert body["design_notes"] == ["Make the hero heading larger.", "Reduce the number of competing colours."]
    assert any(f["highlighted_text"] == "[Website] Images without alt text" for f in body["result"]["findings"])
    assert body["facts"]["imagesMissingAlt"] == 2 and "missingAltExamples" not in body["facts"]
    assert not [q for q in body["result"]["questions"] if q["kind"] == "website"]  # we already have the address


def test_unreachable_sites_give_a_clear_422(client, monkeypatch):
    async def refuse(url):
        raise SiteError("that address isn't a public website")

    monkeypatch.setattr("engano_backend.review_service.render_site", refuse)
    r = client.post("/api/check-website", json={"url": "http://10.0.0.1"})
    assert r.status_code == 422 and "isn't a public website" in r.json()["detail"]


def test_a_broken_design_model_does_not_break_the_check(client, monkeypatch):
    class Broken(Designer):
        def suggest_visual_changes(self, *a):
            raise RuntimeError("the vision model took too long")

    async def fake_render(url):
        return fake_site()

    monkeypatch.setattr("engano_backend.review_service.render_site", fake_render)
    monkeypatch.setattr("ai_engine.providers.factory.get_provider", lambda config=None: Broken())
    body = client.post("/api/check-website", json={"url": "acme.example"}).json()
    assert body["design_notes"] == [] and "took too long" in body["design_error"] and body["result"]["findings"]


def test_url_length_is_limited(client):
    assert client.post("/api/check-website", json={"url": "x" * 3000}).status_code == 422


def test_a_page_stuck_on_its_loading_screen_is_called_out(repo):
    found = titles(check(repo, {"stillLoading": True, "settled": False, "settleSeconds": 25.0}))
    assert "[Website] Still on a loading screen" in found


def test_a_slow_page_is_a_minor_note_and_a_fast_one_is_not(repo):
    assert "[Website] Slow to show content" in titles(check(repo, {"settleSeconds": 9.0, "settled": True}))
    assert titles(check(repo, {"settleSeconds": 1.2, "settled": True})) == []


def test_websites_skip_the_slow_ai_second_opinion_but_keep_every_rule_check(repo):
    class Counting(BaseProvider):
        provider_name = "counting"
        reviewed = 0
        looked = 0

        def review(self, *a, **k):
            Counting.reviewed += 1
            return ProviderResponse(provider_name="counting")

        def understand_image(self, *a):
            Counting.looked += 1
            return None

        def generate_rewrite(self, *a, **k):
            Counting.rewrote = getattr(Counting, "rewrote", 0) + 1
            return None

    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=Counting(), retriever=None)
    shots = [ImageItem(alt_text="s", metadata={"base64": png_b64(), "skip_understanding": True}) for i in range(3)]
    result = agent.run_review(DraftPayload(
        draft_id="s", brand_id="nimbus_cloud", content_text="NimbusDB has 100% uptime.", images=shots,
        metadata={"website_facts": CLEAN_FACTS}, answers={"website": "https://a.example/"},
    ))
    assert Counting.reviewed == 0 and Counting.looked == 0           # no AI second opinion on page text, no per-screenshot look
    assert getattr(Counting, "rewrote", 0) == 0                      # and no AI rewrite of a whole website
    assert {"terminology", "wrong_fact"} <= {f.category.value for f in result.findings}


def decision(result):
    return result.decision.status.value


def test_a_site_with_only_minor_problems_is_never_ready_to_publish(repo):
    result = check(repo, {"description": ""})  # a single LOW finding
    assert titles(result) == ["[Website] No page description"]
    assert decision(result) == "YELLOW"


def test_a_clean_site_is_still_ready(repo):
    assert decision(check(repo, {})) == "GREEN"


@pytest.mark.parametrize("facts", [
    {"imagesMissingAlt": 1}, {"insecure": True}, {"zoomBlocked": True}, {"unlabelledFields": 1}, {"autoplayWithSound": 1},
    {"contrastFails": 6, "contrastChecked": 10},
])
def test_serious_site_problems_need_a_reviewer(repo, facts):
    result = check(repo, facts)
    assert decision(result) == "RED"


def test_a_few_contrast_failures_are_medium_and_many_are_high(repo):
    few = next(f for f in check(repo, {"contrastFails": 2}).findings if f.highlighted_text == "[Website] Low text contrast")
    many = next(f for f in check(repo, {"contrastFails": 5}).findings if f.highlighted_text == "[Website] Low text contrast")
    assert (few.severity.value, many.severity.value) == ("medium", "high")


def test_every_website_finding_says_what_is_wrong_and_what_to_fix(repo):
    worst = {
        "httpStatus": 500, "blocked": "captcha", "loginWall": True, "nearlyEmpty": True, "brokenLinkCount": 1, "brokenLinks": ["404 x"],
        "brokenImages": 1, "pageErrors": 1, "mobileOverflowPx": 50, "imagesMissingAlt": 1, "contrastFails": 1, "unlabelledFields": 1,
        "unnamedButtons": 1, "zoomBlocked": True, "insecure": True, "title": "", "h1": 0, "lang": "", "viewportMeta": False,
    }
    found = [f for f in check(repo, worst).findings if f.highlighted_text.startswith("[Website]")]
    assert len(found) >= 12
    for f in found:
        assert f.explanation.startswith("Problem: ") and " Fix required: " in f.explanation, f.highlighted_text


def test_a_site_that_cannot_be_seen_is_fixed_by_its_owner_not_judged_by_a_reviewer(repo):
    result = check(repo, {"blocked": "access denied", "nearlyEmpty": True})
    assert result.decision.status.value == "RED"
    assert result.decision.action_required_by.value == "creator_question"
    assert "must fix" in result.decision.reason


def test_text_problems_still_go_to_a_reviewer_even_on_a_site_with_site_problems(repo):
    result = check(repo, {"insecure": True}, text="NimbusDB has 100% uptime. Try it free forever.")
    assert result.decision.status.value == "RED"
    assert result.decision.action_required_by.value == "reviewer_approval"
