"""Channel adapter factory."""

from typing import Union
from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.adapters.discord import DiscordAdapter
from ai_engine.adapters.gmail import GmailAdapter
from ai_engine.adapters.linkedin import LinkedInAdapter
from ai_engine.adapters.web_studio import WebStudioAdapter
from ai_engine.adapters.whatsapp import WhatsAppAdapter
from ai_engine.schemas.payload import ChannelType


_ADAPTERS = {
    ChannelType.WEB_STUDIO: WebStudioAdapter,
    ChannelType.DISCORD: DiscordAdapter,
    ChannelType.WHATSAPP: WhatsAppAdapter,
    ChannelType.GMAIL: GmailAdapter,
    ChannelType.LINKEDIN: LinkedInAdapter,
}


def get_adapter(channel: Union[ChannelType, str]) -> BaseChannelAdapter:
    """Resolve the channel adapter instance for a given channel."""
    if isinstance(channel, str):
        try:
            channel = ChannelType(channel.lower())
        except ValueError:
            raise ValueError(f"Unsupported channel '{channel}'. Supported: {[c.value for c in ChannelType]}")

    adapter_cls = _ADAPTERS.get(channel)
    if not adapter_cls:
        raise ValueError(f"No adapter registered for channel {channel}")
    return adapter_cls()
