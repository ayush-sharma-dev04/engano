import discord


class ReviewActions(discord.ui.View):
    """Buttons under every brand-check reply.

    Persistent (timeout=None with fixed custom_ids), so buttons on old
    replies keep working after the bot restarts.
    """

    def __init__(self, studio_url: str | None = None):
        super().__init__(timeout=None)
        if studio_url:
            self.add_item(discord.ui.Button(label="Open in studio", url=studio_url))

    @discord.ui.button(
        label="Request review",
        style=discord.ButtonStyle.primary,
        custom_id="engano:request_review",
    )
    async def request_review(self, interaction: discord.Interaction, _button: discord.ui.Button):
        bot = interaction.client
        reviewer_id = getattr(getattr(bot, "escalation", None), "discord_user_id", None)
        if not reviewer_id:
            await interaction.response.send_message(
                "No reviewer is configured (ENGANO_REVIEWER_DISCORD_ID). Nothing was sent.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        embeds = interaction.message.embeds[:1] if interaction.message else []
        sent = await bot.send_to_reviewer(
            f"ENGANO: <@{interaction.user.id}> asked you to review this draft check.", embeds[0] if embeds else None
        )
        await interaction.followup.send(
            "Sent to the reviewer." if sent else "I couldn't reach the reviewer. Please contact them directly.",
            ephemeral=True,
        )
