import os
import discord
from utils.bot import SurveyWolf

COGS = ["utility", "survey"]

intents = discord.Intents.default()

try:
    debug_guilds = [os.environ["debug_guilds"]]
except KeyError:
    debug_guilds = None

bot = SurveyWolf(description="Make Surveys To Get Quick Opinions And Data",
                 intents=intents,
                 debug_guilds=debug_guilds
                 )
for cog in COGS:
    bot.load_extension(f"cogs.{cog}", store=False)


@bot.event
async def on_ready():
    print("Logged In")

bot.run(os.environ["bot_token"])
