import discord
from discord import slash_command, Option
from discord.ext import pages
from utils.database import database as db
from utils import embed_factory as ef
from utils.db_classes import BaseQuestion, SurveyResponse, gather_questions
from cogs.survey.old_survey import survey_name_autocomplete, get_survey

class ResultsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(description="View The Results And Responses Of A Survey")
    @discord.default_permissions(manage_guild=True)
    async def results(
            self,
            ctx,
            survey: Option(
                str,
                description="The Survey To See The Results Of",
                autocomplete=survey_name_autocomplete,
            ),
            grouped: Option(
                str,
                description="How Should The Results Be Grouped",
                choices=[
                    discord.OptionChoice("By Template", "0"),
                    discord.OptionChoice("By Instance", "1"),
                    discord.OptionChoice("By User", "2"),
                ],
                required=False,
                default="0",
            ),
    ):
        survey_row = await get_survey(survey, ctx)
        if survey_row is None:
            return

        # sql = """SELECT id FROM surveys.guild_surveys WHERE guild_id = $1 AND name = $2;"""
        # survey_row = await db.fetch(sql, ctx.guild.id, survey)

        # Get Questions
        sql = """SELECT id, type, text, position FROM surveys.questions WHERE survey_id=$1"""
        questions: list[BaseQuestion] | BaseQuestion = await gather_questions(await db.fetch(sql, survey_row.id))
        if not isinstance(questions, list):
            questions = [questions]
        questions: dict[int, BaseQuestion] = {q.q_id: q for q in questions}

        survey_description = discord.Embed(
            title=f"Results For {survey}",
            description="\n".join([f"{q.pos}. {q.text}" for q in questions.values()]),
        )

        if grouped == "0":
            sql = """SELECT user_id, question_id, response FROM surveys.responses 
                WHERE question_id IN (SELECT id FROM surveys.questions WHERE survey_id=$1)
                ORDER BY question_id;"""
        elif grouped == "1":
            sql = """SELECT user_id, question_id, response FROM surveys.responses 
                WHERE question_id IN (SELECT id FROM surveys.questions WHERE survey_id=$1)
                ORDER BY active_survey_id, question_id;"""
        elif grouped == "2":
            sql = """SELECT user_id, question_id, response FROM surveys.responses 
                WHERE active_survey_id IN (SELECT id FROM surveys.active_guild_surveys WHERE template_id=$1)
                ORDER BY user_id, question_id;"""
        else:
            return
        responses: list[SurveyResponse] = await SurveyResponse.from_db_row(await db.fetch(sql, survey_row.id))
        if not responses:
            return await ctx.respond(
                embed=await ef.fail("There Are No Responses To This Survey Yet"),
                ephemeral=True,
            )

        # Splits The Responses Into Easily Readable Chunks.
        embeds = []
        e = discord.Embed()
        current_length = 0
        for response in responses:
            if current_length + len(response.response) > 1024 or len(e.fields) >= 8:
                embeds.append([survey_description, e])
                e = discord.Embed()
                current_length = 0
            e.add_field(
                name=f"Question {questions[response.question_id].pos + 1}",
                value=f"From <@{response.user_id}>\n{response.response}",
                inline=False,
            )
            current_length += len(response.response)
        if e.fields:
            embeds.append([survey_description, e])

        pgn = pages.Paginator(pages=embeds)
        await pgn.respond(ctx.interaction, ephemeral=True)

def setup(bot):
    bot.add_cog(ResultsCog(bot))