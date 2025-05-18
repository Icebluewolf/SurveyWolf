import discord
from discord import ApplicationContext

from utils.bot import SurveyWolf
from main import bot as survey_wolf_bot


class Developer(discord.Cog, guild_ids=survey_wolf_bot.config["dev_guilds"]):
    def __init__(self, bot):
        self.bot: SurveyWolf = bot

    log_text = {
        "error_logging_webhook": "Errors",
        "server_join_leave_webhook": "Guild Join/Leave",
    }
    logs = [discord.OptionChoice(x[1], x[0]) for x in log_text.items()]
    logging = discord.SlashCommandGroup("logging", "Actions For The Discord Facing Logging")

    async def cog_before_invoke(self, ctx: ApplicationContext) -> None:
        if ctx.guild_id not in self.bot.config["dev_guilds"]:
            raise Exception("Guild Not Authorized To Run Developer Command")

        if not await self.bot.is_owner(ctx.user):
            raise Exception("User Not Authorized To Run Developer Command")

    @discord.Cog.listener()
    async def on_guild_join(self, guild):
        await self.bot.config["server_join_leave_webhook"].send(
            f"Joined A New Server: {guild.id} Total: {len(self.bot.guilds)}"
        )

    @discord.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot.config["server_join_leave_webhook"].send(
            f"Left A Server: {guild.id} Total: {len(self.bot.guilds)}"
        )

    async def _remove_webhook(self, w: discord.Webhook | None):
        if w is not None:
            try:
                if w.is_partial():
                    w = await self.bot.fetch_webhook(w.id)
                await w.delete(reason="Logging Moved Or Disabled")
            except discord.NotFound:
                pass

    @logging.command(description="Creates A Webhook In The Current Channel For The Specified Log")
    async def set(
        self, ctx: discord.ApplicationContext, log: discord.Option(str, description="The Log To Set", choices=logs)
    ):
        w = await ctx.channel.create_webhook(
            name=f"{self.bot.user.name} {self.log_text[log]} Log",
            avatar=await self.bot.user.avatar.read() if self.bot.user.avatar else None,
            reason="Logging Enabled",
        )
        await self._remove_webhook(self.bot.config[log])
        self.bot.update_config(log, w, w.url)
        await ctx.respond("Logging Set", ephemeral=True)

    @logging.command(description="Removes The Webhook For The Specified Log")
    async def unset(
        self, ctx: discord.ApplicationContext, log: discord.Option(str, description="The Log To Remove", choices=logs)
    ):
        await self._remove_webhook(self.bot.config[log])
        self.bot.update_config(log, None, "None")
        await ctx.respond("Logging Unset", ephemeral=True)


def setup(bot):
    bot.add_cog(Developer(bot))
