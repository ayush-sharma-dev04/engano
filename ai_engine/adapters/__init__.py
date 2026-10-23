"""Channel adapters package for Engano AI Review Engine."""

from ai_engine.adapters.base import BaseChannelAdapter
from ai_engine.adapters.discord import DiscordAdapter
from ai_engine.adapters.factory import get_adapter
from ai_engine.adapters.gmail import GmailAdapter
from ai_engine.adapters.linkedin import LinkedInAdapter
from ai_engine.adapters.web_studio import WebStudioAdapter
from ai_engine.adapters.whatsapp import WhatsAppAdapter

__all__ = [
    "BaseChannelAdapter",
    "DiscordAdapter",
    "GmailAdapter",
    "LinkedInAdapter",
    "WebStudioAdapter",
    "WhatsAppAdapter",
    "get_adapter",
]
