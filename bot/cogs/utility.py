import discord
from discord import slash_command
from utils import component_factory as ef


class Utility(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command()
    async def ping(self, ctx):
        await ctx.respond(
            view=discord.ui.View(await ef.general("🏓 Ping", str(self.bot.latency * 1000)), timeout=0),
            ephemeral=True,
        )

    @slash_command()
    async def info(self, ctx):
        desc = (
            "Survey Wolf is a highly customizable application to offer surveys directly on Discord.\n"
            "- To create your first survey use the `/create` command.\n"
            "- To send this survey use the `/send` command.\n"
            "- To view the results use the `/results` command.\n"
            "Survey Wolf aims to offer an easy to use interface to allow Discord server managers to collect "
            "feedback about their members. If you have any specific requests please join the support server and "
            "we will do our best to assist you."
        )

        c = await ef.general(
            title=self.bot.user.name
            + (f"#{self.bot.user.discriminator}" if self.bot.user.discriminator != "0" else ""),
            message=desc,
        )
        c.add_text(
            "### Support\nIf You Have An Issue With The Bot Please Join The Support Server [Here]("
            'https://discord.gg/f39cJ9D/ "Survey Wolf Official Support Server")',
        )
        c.add_text("### Credits\nMain Bot Developer: icewolfy (451848182327148554)")
        c.add_text("### Technical\nUses Python V3 And [Pycord](https://pycord.dev/) V2. Database: PostgreSQL")
        c.add_text("### Hosting\nHosted On Digital Ocean")
        c.add_text("### Documents\n"
                   "[Privacy Policy](https://gist.github.com/Icebluewolf/90335bbc4d82d435d437b5da98f71df6)\n"
                   "[Terms Of Service](https://gist.github.com/Icebluewolf/7e73be418408ac48a35deb8045ae2a29)")
        await ctx.respond(view=discord.ui.View(c, timeout=0), ephemeral=True)


def setup(bot):
    bot.add_cog(Utility(bot))
