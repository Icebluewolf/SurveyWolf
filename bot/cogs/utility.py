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
        # Totally Not Made By ChatGPT
        desc = (
            "Survey Wolf is designed to make survey creation and hosting a breeze. With Survey Wolf, users can "
            "easily create and customize surveys within Discord, allowing for easy access and engagement. The bot "
            "is almost fully customizable, allowing users to tailor surveys to their specific needs and "
            "preferences. Whether you're conducting market research, gathering feedback, or just wanting to get a "
            "better understanding of your community's preferences, Survey Wolf makes it easy to get the insights "
            "you need. With its user-friendly interface and customizable options, Survey Wolf is the perfect tool "
            "for any Discord server looking to engage its members in meaningful conversations. "
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
        e.add_field(name="Technical", value="Uses Python V3 And Pycord V2. Database: PostgreSQL")
        e.add_field(
            name="Hosting",
            value="Hosted On *To Be Determined*",
        )
        await ctx.respond(embed=e, ephemeral=True)


def setup(bot):
    bot.add_cog(Utility(bot))
