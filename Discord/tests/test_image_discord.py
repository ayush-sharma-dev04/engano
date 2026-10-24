"""Discord: attachments are read with a size cap; the bytes reach the engine."""

import asyncio
import base64
from types import SimpleNamespace

from engano_backend.review_service import ReviewService, ReviewSettings
from engano_discord.bot import MAX_IMAGE_BYTES, read_attachment
from engano_discord.review import Draft, to_payload


def run(coro):
    return asyncio.run(coro)


class Att:
    def __init__(self, size, data=b"bytes", fail=False):
        self.size, self._data, self._fail = size, data, fail

    async def read(self):
        if self._fail:
            raise RuntimeError("gone")
        return self._data


def test_attachments_over_the_cap_are_not_downloaded():
    assert run(read_attachment(Att(MAX_IMAGE_BYTES + 1))) is None


def test_small_attachments_are_read_and_failures_are_swallowed():
    assert run(read_attachment(Att(10, b"abc"))) == b"abc"
    assert run(read_attachment(Att(10, fail=True))) is None


def test_bytes_end_up_on_the_payload_image():
    reviews = ReviewService(ReviewSettings(brand_id="nimbus_cloud", policy_source="fixture"))
    draft = Draft(channel="discord", author_id="1", text="hi", image_urls=["https://cdn.discordapp.com/a.png"],
                  image_alt_texts=["A banner"], image_data=[b"\x89PNGdata"])
    payload = to_payload(reviews, draft, "discord-1")
    assert base64.b64decode(payload.images[0].metadata["base64"]) == b"\x89PNGdata"
    assert payload.images[0].alt_text == "A banner"
