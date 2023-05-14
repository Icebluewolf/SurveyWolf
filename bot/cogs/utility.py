import discord
from discord import slash_command
from bot.utils import embed_factory as ef


class Utility(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command()
    async def ping(self, ctx):
        await ctx.send(embed=await ef.error(str(self.bot.latency * 1000)), ephemeral=True)

    @slash_command()
    async def info(self, ctx):
        # Totally Not Made By ChatGPT
        desc = "Survey Wolf is designed to make survey creation and hosting a breeze. With Survey Wolf, users can " \
               "easily create and customize surveys within Discord, allowing for easy access and engagement. The bot " \
               "is almost fully customizable, allowing users to tailor surveys to their specific needs and " \
               "preferences. Whether you're conducting market research, gathering feedback, or just wanting to get a " \
               "better understanding of your community's preferences, Survey Wolf makes it easy to get the insights " \
               "you need. With its user-friendly interface and customizable options, Survey Wolf is the perfect tool " \
               "for any Discord server looking to engage its members in meaningful conversations. "

        e = await ef.general(title="SurveyWolf#2938", message=desc)
        e.add_field(name="Support", value="If You Have An Issue With The Bot Please Join The Support Server [Here]("
                                          "https://discord.gg/f39cJ9D/ \"Survey Wolf Official Support Server\")")
        e.add_field(name="Credits", value="Main Bot Developer: Ice Wolfy#5283 (451848182327148554)")
        e.add_field(name="Technical", value="Uses Python V3 And Pycord V2")
        e.add_field(name="Hosting", value="Hosted On A [PloxHost](https://billing.plox.host/aff.php?aff=162 "
                                          "\"Affiliate Link\") VPS Running Linux")
        await ctx.respond(embed=e, ephemeral=True)

    @slash_command(guild_ids=[678359965081141286])
    async def test(self, ctx):
        await ctx.send(embed=await ef.general(title="respond", message=""))

    def test_callback(self, printable):
        print(printable)

    @slash_command(guild_ids=[678359965081141286])
    async def test2(self, ctx, cog: str):
        print("Number Commands: ", sum(1 for _ in self.bot.walk_application_commands()))
        self.bot.unload_extension(f"cogs.{cog}")
        print("Number Commands: ", sum(1 for _ in self.bot.walk_application_commands()))
        await self.bot.sync_commands()
        print("Number Commands: ", sum(1 for _ in self.bot.walk_application_commands()))

    # Testing For Making A Close Thread Listener
    # @discord.Cog.listener()
    # async def on_thread_update(self, before, after):
    #     minutes_to_str = {60: "1 Hour", 1440: "24 Hours", 4320: "3 Days", 10080: "1 Week"}
    #     description = ""
    #     user = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.thread_update).flatten()
    #     user = user[0].user
    #
    #     if before.archived and not after.archived:
    #         # If A Message Was Sent That Caused The Unarchive No Need To Send A Message To Say Who Did It
    #         print(before.total_message_sent)
    #         print(after.total_message_sent)
    #         if before.total_message_sent == after.total_message_sent:
    #             description += "Reopened This Thread.\n"
    #
    #     if before.auto_archive_duration != after.auto_archive_duration:
    #         description += f"Set The Auto Archive Time To {minutes_to_str[after.auto_archive_duration]}"
    #
    #     if description:
    #         e = discord.Embed(title=f"Thread Updated By {user}", description=description)
    #         await after.send(embed=e)
    #
    #     # Give warning message with original message instead. View to delete this message?
    #     if after.starting_message is None:
    #         await after.archive()


def setup(bot):
    bot.add_cog(Utility(bot))
