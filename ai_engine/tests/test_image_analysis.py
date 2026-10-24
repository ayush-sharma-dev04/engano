"""Image checks: safe decoding, text in images, real contrast, logos, alt text."""

import base64
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from ai_engine.agents.coordinator import CoordinatorAgent
from ai_engine.config import EngineConfig
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.base import BaseProvider, ProviderResponse
from ai_engine.providers.factory import RulesOnlyProvider
from ai_engine.schemas.payload import DraftPayload, ImageItem
from ai_engine.schemas.vision import ImageUnderstanding, LogoSighting
from ai_engine.vision import imaging, ocr

needs_tesseract = pytest.mark.skipif(not ocr.tesseract_available(), reason="tesseract not installed")


def b64(img: Image.Image, fmt="PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def banner(text, fg=(0, 0, 0), bg=(255, 255, 255), size=56, width=1100, height=220) -> Image.Image:
    img = Image.new("RGB", (width, height), bg)
    ImageDraw.Draw(img).text((30, 60), text, fill=fg, font=ImageFont.load_default(size=size))
    return img


def item(img, alt=None, **meta) -> ImageItem:
    return ImageItem(alt_text=alt, metadata={"base64": b64(img), **meta})


class Stub(BaseProvider):
    """Stands in for the vision model."""

    provider_name = "stub"

    def __init__(self, understanding=None, error=None):
        self.understanding, self.error, self.calls = understanding, error, 0

    def review(self, content_text, policy, deterministic_findings, images=None, context=None):
        return ProviderResponse(provider_name="stub")

    def understand_image(self, image_b64, alt_text, width, height):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return self.understanding


@pytest.fixture
def repo():
    r = MockPolicyRepository()
    r.load_fixture("data/brand_library/nimbus_db.json")
    return r


def review(repo, images, provider=None, text="Our new banner."):
    agent = CoordinatorAgent(repo, config=EngineConfig(), provider=provider or RulesOnlyProvider(), retriever=None)
    return agent.run_review(DraftPayload(draft_id="i", brand_id="nimbus_cloud", content_text=text, images=images))


# ------------------------------------------------------------------ decoding


def test_valid_images_decode_and_transparency_is_flattened():
    rgba = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    out = imaging.decode_image(b64(rgba))
    assert out.image.mode == "RGB" and out.image.getpixel((5, 5)) == (255, 255, 255) and out.mime == "image/png"
    assert imaging.decode_image(b64(Image.new("RGB", (10, 10)), "GIF")).mime == "image/gif"


@pytest.mark.parametrize("data", [
    "not base64!!", "", base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'/>").decode(),
    base64.b64encode(b"%PDF-1.4 hello").decode(), base64.b64encode(b"\x89PNG\r\n\x1a\nbroken").decode(),
])
def test_unusable_files_are_refused(data):
    with pytest.raises(imaging.ImageError):
        imaging.decode_image(data)


def test_oversized_files_are_refused():
    with pytest.raises(imaging.ImageError, match="MB"):
        imaging.decode_image(base64.b64encode(b"x" * (imaging.MAX_IMAGE_BYTES + 1)).decode())


def test_decompression_bombs_are_refused():
    bomb = Image.new("1", (6000, 6000))  # 36M pixels, tiny when compressed
    with pytest.raises(imaging.ImageError, match="too large"):
        imaging.decode_image(b64(bomb))


# ------------------------------------------------------------------ pixel measurements


def test_contrast_ratio_matches_wcag_reference_values():
    assert imaging.contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert imaging.contrast_ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.05)


def test_clear_space_around_a_logo():
    quiet = Image.new("RGB", (400, 300), "white")
    ImageDraw.Draw(quiet).rectangle((150, 100, 250, 160), fill=(20, 40, 160))
    assert imaging.clear_space_met(quiet, [150, 100, 250, 160]) is True

    crowded = quiet.copy()
    d = ImageDraw.Draw(crowded)
    for x in range(110, 300, 6):
        d.line((x, 80, x, 180), fill=(200, 30, 30), width=3)
    d.rectangle((150, 100, 250, 160), fill=(20, 40, 160))
    assert imaging.clear_space_met(crowded, [150, 100, 250, 160]) is False

    assert imaging.clear_space_met(quiet, [0, 0, 100, 60]) is False       # logo jammed into the corner
    assert imaging.clear_space_met(quiet, [10, 10, 5000, 60]) is None      # box can't be trusted


# ------------------------------------------------------------------ whole pipeline


@needs_tesseract
def test_text_inside_an_image_is_checked_like_the_draft(repo):
    result = review(repo, [item(banner("NimbusDB has 100% uptime"))])
    image_findings = [f for f in result.findings if f.highlighted_text.startswith("[Image 1] ")]
    cats = {f.category.value for f in image_findings}
    assert {"terminology", "wrong_fact"} <= cats
    assert all(f.highlighted_text.startswith("[Image 1] ") and f.human_review_required for f in image_findings)
    assert any("Suggested change" in f.explanation for f in image_findings)
    assert result.decision.status.value == "RED"


@needs_tesseract
def test_low_contrast_text_is_measured_from_the_pixels(repo):
    faint = banner("Nimbus DB is a reliable platform", fg=(205, 205, 205))
    result = review(repo, [item(faint)])
    contrast = [f for f in result.findings if "contrast" in f.explanation.lower() and f.image_index == 1]
    assert contrast and contrast[0].severity.value == "high"


@needs_tesseract
def test_readable_text_passes_contrast(repo):
    result = review(repo, [item(banner("Nimbus DB is a reliable platform"), alt="A banner")])
    assert not [f for f in result.findings if "contrast" in f.explanation.lower()]


def test_missing_alt_text_comes_with_a_suggestion_from_the_picture(repo):
    stub = Stub(ImageUnderstanding(description="A dashboard showing database latency."))
    result = review(repo, [item(Image.new("RGB", (300, 200), "white"))], provider=stub)
    f = next(f for f in result.findings if f.suggested_alt)
    assert f.suggested_alt == "A dashboard showing database latency." and "Suggested alt text" in f.explanation and f.image_index == 1


def test_alt_text_that_does_not_match_is_flagged(repo):
    stub = Stub(ImageUnderstanding(description="A cat on a sofa.", alt_text_matches=False, alt_text_reason="it shows a cat"))
    result = review(repo, [item(Image.new("RGB", (300, 200), "white"), alt="Database dashboard")], provider=stub)
    f = next(f for f in result.findings if "alt text" in f.explanation.lower() and "match" in f.explanation.lower())
    assert f.suggested_alt == "A cat on a sofa." and f.human_review_required


def test_other_companies_logos_are_flagged_but_the_brand_and_partners_are_not(repo):
    stub = Stub(ImageUnderstanding(description="x", logos=[LogoSighting(name="Acme Corp"), LogoSighting(name="Nimbus DB")]))
    result = review(repo, [item(Image.new("RGB", (300, 200), "white"), alt="x")], provider=stub)
    third = [f for f in result.findings if f.category.value == "legal" and f.image_index == 1]
    assert len(third) == 1 and "Acme Corp" in third[0].explanation

    repo.get_policy("nimbus_cloud").logo_rules.approved_partners.append("Acme Corp")
    result = review(repo, [item(Image.new("RGB", (300, 200), "white"), alt="x")], provider=stub)
    assert not [f for f in result.findings if "Acme" in f.explanation]


def test_missing_brand_logo_is_flagged_only_when_the_policy_requires_it(repo):
    stub = Stub(ImageUnderstanding(description="x"))
    pic = [item(Image.new("RGB", (300, 200), "white"), alt="x")]
    assert not [f for f in review(repo, pic, provider=stub).findings if "logo was not found" in f.explanation]
    repo.get_policy("nimbus_cloud").logo_rules.require_brand_logo = True
    assert [f for f in review(repo, pic, provider=stub).findings if "logo was not found" in f.explanation]


def test_a_failing_vision_model_is_reported_never_silently_passed(repo):
    result = review(repo, [item(Image.new("RGB", (300, 200), "white"), alt="x")], provider=Stub(error="the vision model took too long"))
    assert any("could not look at this image" in f.explanation for f in result.findings)
    assert result.decision.status.value != "GREEN"


def test_an_unreadable_image_is_reported(repo):
    result = review(repo, [ImageItem(alt_text="x", metadata={"base64": "not-an-image"})])
    assert any("could not be checked" in f.explanation for f in result.findings)


def test_rules_only_mode_never_calls_a_model(repo):
    stub = Stub(ImageUnderstanding(description="x"))
    review(repo, [item(Image.new("RGB", (100, 100), "white"), alt="x")], provider=RulesOnlyProvider())
    assert stub.calls == 0


def test_real_providers_actually_implement_image_understanding():
    """Guards against the method silently falling back to the 'cannot look at images' default."""
    from ai_engine.providers.gemini import GeminiProvider
    from ai_engine.providers.ollama import OllamaProvider

    assert OllamaProvider.understand_image is not BaseProvider.understand_image
    assert GeminiProvider.understand_image is not BaseProvider.understand_image


def test_alt_text_overlap_check_does_not_trust_the_model():
    from ai_engine.vision.analyzer import alt_text_disagrees

    desc, text = "An advertisement for a database service, highlighting its speed.", "Nimbus DB fastest database"
    assert alt_text_disagrees("A photo of a cat", desc, text) is False  # one content word only: too little to judge
    assert alt_text_disagrees("A fluffy orange kitten sleeping", desc, text) is True
    assert alt_text_disagrees("Database service advertisement", desc, text) is False
    assert alt_text_disagrees("Dashboard", desc, text) is False


@needs_tesseract
def test_brand_wordmark_in_the_image_counts_as_the_logo_and_clear_space_is_measured(repo):
    repo.get_policy("nimbus_cloud").logo_rules.require_brand_logo = True
    plain = Image.new("RGB", (900, 400), "white")
    ImageDraw.Draw(plain).text((300, 160), "Nimbus DB", fill=(20, 40, 160), font=ImageFont.load_default(size=64))
    stub = Stub(ImageUnderstanding(description="A company name on a white background."))  # model sees no logo
    result = review(repo, [item(plain, alt="Nimbus DB wordmark on white background")], provider=stub)
    assert not [f for f in result.findings if "logo was not found" in f.explanation]
    assert not [f for f in result.findings if "clear-space" in f.explanation.lower()]

    crowded = plain.copy()
    d = ImageDraw.Draw(crowded)
    font = ImageFont.load_default(size=64)
    left, top, right, bottom = d.textbbox((300, 160), "Nimbus DB", font=font)
    for box in (  # solid shapes hugging the wordmark, inside the clear-space margin
        (left - 14, top - 14, left - 4, bottom + 14), (right + 4, top - 14, right + 14, bottom + 14),
        (left - 14, top - 14, right + 14, top - 4), (left - 14, bottom + 4, right + 14, bottom + 14),
    ):
        d.rectangle(box, fill=(200, 30, 30))
    d.text((300, 160), "Nimbus DB", fill=(20, 40, 160), font=font)
    result = review(repo, [item(crowded, alt="Nimbus DB wordmark on striped background")], provider=stub)
    assert [f for f in result.findings if "clear-space" in f.explanation.lower()]


def _words_box(img, text, xy, font):
    d = ImageDraw.Draw(img)
    return d.textbbox(xy, text, font=font)


@pytest.mark.parametrize("size", [12, 14, 16, 22, 40])
def test_thin_dark_text_on_light_grey_is_not_reported_as_low_contrast(size):
    """Regression: dominant-colour clustering read this as ~2:1 and raised false accessibility alarms."""
    img = Image.new("RGB", (600, 120), (240, 240, 242))
    font = ImageFont.load_default(size=size)
    ImageDraw.Draw(img).text((20, 30), "This domain is for use in documentation", fill=(32, 33, 36), font=font)
    box = _words_box(img, "This domain is for use in documentation", (20, 30), font)
    assert imaging.region_contrast(img, box) > 10


@pytest.mark.parametrize("fg,bg,expected", [
    ((205, 205, 205), (255, 255, 255), 1.5),     # pale grey on white: genuinely poor
    ((119, 119, 119), (255, 255, 255), 4.48),    # the WCAG boundary grey
    ((255, 255, 255), (30, 60, 200), 7.0),       # white on blue, light on dark
])
def test_measured_contrast_tracks_the_real_ratio(fg, bg, expected):
    img = Image.new("RGB", (700, 160), bg)
    font = ImageFont.load_default(size=64)
    ImageDraw.Draw(img).text((20, 30), "Nimbus platform", fill=fg, font=font)
    box = _words_box(img, "Nimbus platform", (20, 30), font)
    assert imaging.region_contrast(img, box) == pytest.approx(imaging.contrast_ratio(fg, bg), rel=0.15)
    assert imaging.region_contrast(img, box) == pytest.approx(expected, rel=0.25)


def test_an_empty_region_has_no_contrast():
    assert imaging.region_contrast(Image.new("RGB", (200, 80), "white"), (10, 10, 150, 60)) is None
