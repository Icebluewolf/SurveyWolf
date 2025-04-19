import discord
from discord import slash_command
from utils import embed_factory as ef


class Utility(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command()
    async def ping(self, ctx):
        await ctx.respond(
            embed=await ef.general("🏓 Ping", str(self.bot.latency * 1000)),
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

        e = await ef.general(
            title=self.bot.user.name
            + (f"#{self.bot.user.discriminator}" if self.bot.user.discriminator != "0" else ""),
            message=desc,
        )
        e.add_field(
            name="Support",
            value="If You Have An Issue With The Bot Please Join The Support Server [Here]("
            'https://discord.gg/f39cJ9D/ "Survey Wolf Official Support Server")',
        )
        e.add_field(name="Credits", value="Main Bot Developer: icewolfy (451848182327148554)")
        e.add_field(name="Technical", value="Uses Python V3 And [Pycord](https://pycord.dev/) V2. Database: PostgreSQL")
        e.add_field(
            name="Hosting",
            value="Hosted On Digital Ocean",
        )
        e.add_field(
            name="Documents",
            value="""[Privacy Policy](https://gist.github.com/Icebluewolf/90335bbc4d82d435d437b5da98f71df6)
            [Terms Of Service](https://gist.github.com/Icebluewolf/7e73be418408ac48a35deb8045ae2a29)""",
        )
        await ctx.respond(embed=e, ephemeral=True)


def setup(bot):
    bot.add_cog(Utility(bot))
