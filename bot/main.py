import os
from dotenv import load_dotenv
import discord
from utils.bot import SurveyWolf

load_dotenv()

COGS = ["utility", "survey.creation", "survey.active", "survey.results"]

intents = discord.Intents.default()

try:
    debug_guilds = [int(os.environ["debug_guilds"])]
except KeyError:
    debug_guilds = None

bot = SurveyWolf(
    description="Make Surveys To Get Quick Opinions And Data",
    intents=intents,
    debug_guilds=debug_guilds,
)
for cog in COGS:
    bot.load_extension(f"cogs.{cog}", store=False)


@bot.listen()
async def on_ready():
    print("Logged In")


bot.run(os.environ["bot_token"])
