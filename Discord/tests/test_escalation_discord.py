"""Discord: the bot DMs the human reviewer; failures are reported, never hidden."""

import asyncio
from types import SimpleNamespace

from engano_backend.escalation import EscalationSettings
from engano_discord.bot import EnganoBot

REVIEWER_ID = 100000000000000001


class FakeUser:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def send(self, content=None, embed=None):
        if self.fail:
            raise RuntimeError("Cannot send messages to this user")
        self.sent.append((content, embed))


def fake_bot(user, reviewer_id=REVIEWER_ID):
    async def fetch_user(uid):
        assert uid == reviewer_id
        return user

    return SimpleNamespace(escalation=EscalationSettings(discord_user_id=reviewer_id), fetch_user=fetch_user)


def run(coro):
    return asyncio.run(coro)


def test_dm_reaches_the_configured_reviewer():
    user = FakeUser()
    assert run(EnganoBot.send_to_reviewer(fake_bot(user), "please review")) is True
    assert user.sent[0][0] == "please review"


def test_closed_dms_return_false_instead_of_raising():
    assert run(EnganoBot.send_to_reviewer(fake_bot(FakeUser(fail=True)), "x")) is False


def test_no_reviewer_configured_sends_nothing():
    bot = fake_bot(FakeUser(), reviewer_id=None)
    assert run(EnganoBot.send_to_reviewer(bot, "x")) is False
