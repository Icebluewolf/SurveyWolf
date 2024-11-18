import discord
from discord.ext import tasks
from utils.database import database as db
from utils import embed_factory as ef
from utils.db_classes import Survey

survey_name_cache: dict[int, list[str]] = {}

MAX_QUESTION_LENGTH = 45
TF_to_YN = {True: "Yes", False: "No"}


def toggle_button(state: bool):
    state = not state
    options = {
        True: [discord.ButtonStyle.green, "✅"],
        False: [discord.ButtonStyle.grey, "❌"],
    }
    return state, options[state][0], options[state][1]

async def survey_name_autocomplete(ctx: discord.AutocompleteContext):
    try:
        results = survey_name_cache[ctx.interaction.guild.id]
    except KeyError:
        sql = "SELECT name FROM surveys.guild_surveys WHERE guild_id = $1;"
        results = [x["name"] for x in await db.fetch(sql, ctx.interaction.guild.id)]
        results = results or ["No Surveys Found. Use /create To Make One"]
        survey_name_cache[ctx.interaction.guild.id] = results
    if results == ["No Surveys Found. Use /create To Make One"]:
        return results
    else:
        return [name for name in results if name.lower().startswith(ctx.value.lower())]


@tasks.loop(minutes=3)
async def _clear_cache():
    global survey_name_cache
    survey_name_cache = {}


async def get_survey(name: str, ctx: discord.ApplicationContext) -> Survey | None:
    if name == "No Surveys Found. Use /create To Make One":
        await ctx.respond(
            embed=await ef.fail("I Told You You Needed To Use /create >:("),
            ephemeral=True,
        )
        return None

    sql = """SELECT id AS template_id, guild_id, anonymous, editable, entries_per, total_entries, time_limit, name 
    FROM surveys.guild_surveys WHERE guild_id = $1 AND name = $2;"""
    survey = await db.fetch(sql, ctx.guild.id, name)
    survey = survey[0]

    if not survey:
        await ctx.respond(
            embed=await ef.fail("There Is No Survey With This Name. Try Selecting One Of The Provided Options."),
            ephemeral=True,
        )
        return None
    return await Survey.from_db_row(survey)