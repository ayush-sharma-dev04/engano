import logging

import discord
from discord import app_commands

from engano_backend.review_service import ReviewService, ReviewSettings

from .config import Settings, load_settings
from .review import Draft, render_result, to_payload
from .views import ReviewActions

log = logging.getLogger("engano.discord")


class EnganoBot(discord.Client):
    def __init__(self, settings: Settings):
        # Interactions carry the content we need, so no privileged intents.
        super().__init__(intents=discord.Intents.default())
        self.settings = settings
        self.reviews = ReviewService(ReviewSettings.from_env())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.add_view(ReviewActions(self.settings.studio_url))
        register_commands(self.tree, self)
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d commands to guild %s", len(synced), self.settings.guild_id)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        log.info(
            "Logged in as %s, checking brand %s (policy source: %s)",
            self.user, self.reviews.settings.brand_id, self.reviews.settings.policy_source,
        )


def register_commands(tree: app_commands.CommandTree, bot: EnganoBot) -> None:
    settings = bot.settings

    async def reply(interaction: discord.Interaction, draft: Draft) -> None:
        if draft.is_empty:
            await interaction.response.send_message(
                "There's nothing to check. Add some text or an image.", ephemeral=True
            )
            return

        # The engine can take longer than Discord's 3 second reply window.
        await interaction.response.defer(ephemeral=True, thinking=True)
        draft_id = f"discord-{interaction.id}"
        try:
            result = await bot.reviews.review_payload(to_payload(bot.reviews, draft, draft_id))
        except Exception:
            log.exception("Review %s failed", draft_id)
            await interaction.followup.send(
                "Something went wrong while reviewing this draft. Nothing was approved. Try again in a moment.",
                ephemeral=True,
            )
            return

        log.info(
            "Review %s by %s: %s (%s, %d findings)",
            draft_id, draft.author_id, result.decision.status.value,
            result.completion_status, len(result.findings),
        )
        await interaction.followup.send(
            embed=render_result(draft, result),
            view=ReviewActions(settings.studio_url),
            ephemeral=True,
        )

    @tree.command(name="brand-check", description="Check a draft against your brand guidelines")
    @app_commands.describe(text="The draft copy to check", image="An image or flyer to check")
    async def brand_check(
        interaction: discord.Interaction,
        text: str | None = None,
        image: discord.Attachment | None = None,
    ):
        if image and not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(
                "That file isn't an image. Attach a PNG, JPG or similar.", ephemeral=True
            )
            return
        await reply(
            interaction,
            Draft(
                channel="discord",
                author_id=str(interaction.user.id),
                text=text or "",
                image_urls=[image.url] if image else [],
                image_alt_texts=[image.description] if image else [],
            ),
        )

    @tree.context_menu(name="Check brand")
    async def check_brand(interaction: discord.Interaction, message: discord.Message):
        images = [a for a in message.attachments if (a.content_type or "").startswith("image/")]
        await reply(
            interaction,
            Draft(
                channel="discord",
                author_id=str(interaction.user.id),
                text=message.content,
                image_urls=[a.url for a in images],
                image_alt_texts=[a.description for a in images],
                source_url=message.jump_url,
            ),
        )

    @tree.command(name="engano-help", description="How to use ENGANO in Discord")
    async def engano_help(interaction: discord.Interaction):
        await interaction.response.send_message(
            "**ENGANO** checks drafts against your brand guidelines before you publish.\n"
            "• `/brand-check text:<draft>` checks a piece of copy. Attach an image to check its alt text too.\n"
            "• Right-click a message → **Apps → Check brand** checks that message.\n"
            "Each finding cites the rule it's based on and suggests a fix. "
            "Nothing is published or approved from Discord. Replies are only visible to you.",
            ephemeral=True,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    EnganoBot(settings).run(settings.bot_token, log_handler=None)


if __name__ == "__main__":
    main()
