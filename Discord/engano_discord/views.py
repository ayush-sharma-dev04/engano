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
        await interaction.response.send_message(
            "Review requests open once the web studio is live. Nothing was sent to a reviewer.",
            ephemeral=True,
        )
