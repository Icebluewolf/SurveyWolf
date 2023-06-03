import os
import discord
from utils.bot import SurveyWolf

COGS = ["utility", "survey"]

intents = discord.Intents.default()
bot = SurveyWolf(description="Make Surveys To Get Quick Opinions And Data",
                 intents=intents,
                 debug_guilds=[678359965081141286])

for cog in COGS:
    bot.load_extension(f"cogs.{cog}", store=False)


@bot.event
async def on_ready():
    print("Logged In")

bot.run(os.environ["bot_token"])
