from collections import defaultdict

import discord
from discord import slash_command, Option
from discord.ext import pages

from forms.survey.template import title_autocomplete, get_templates
from questions.survey_question import from_db, SurveyQuestion, fetch_template_questions, fetch_question_responses
from utils.database import database as db
from utils import embed_factory as ef


class ResultsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(description="View The Results And Responses Of A Survey")
    @discord.default_permissions(manage_guild=True)
    async def results(
        self,
        ctx,
        name: Option(
            str,
            description="The Survey To See The Results Of",
            autocomplete=title_autocomplete,
        ),
        grouped: Option(
            str,
            description="How Should The Results Be Grouped",
            choices=[
                discord.OptionChoice("By Question", "0"),
                discord.OptionChoice("By Response", "1"),
                # discord.OptionChoice("By Survey Instance", "2"),
            ],
            required=False,
            default="0",
        ),
    ):
        await ctx.defer(ephemeral=True)
        templates = await get_templates(ctx.guild_id)
        for template in templates:
            if name == str(template._id) or name == template.title:
                break
        else:
            return await ctx.respond(embed=await ef.fail(f"No Survey Named `{name}` Found"), ephemeral=True)

        # Get Questions
        questions: list[SurveyQuestion] = await fetch_template_questions(template._id)
        questions.sort(key=lambda x: x.position)

        # Get Responses
        responses = await fetch_question_responses(questions)
        if len(responses) == 0:
            return await ctx.respond(
                embed=await ef.fail("There Are No Responses To This Survey Yet"),
                ephemeral=True,
            )

        if grouped == "0":
            response_map = defaultdict(list)

            for response in responses:
                response_map[response["question"]].append(response)

            page_groups = []
            for question in questions:
                question_embed = await question.display()
                e = discord.Embed(title="Responses", description="")
                embeds = []
                for response in response_map[question._id]:
                    r = await question.view_response(response)
                    if len(r) == 0:
                        continue
                    response = "- " + discord.utils.escape_markdown(r)
                    if len(e.description) != 0 and len(e) + len(response) > 1024:
                        embeds.append(pages.Page(embeds=[question_embed, e]))
                        e = discord.Embed(title="Responses", description="")
                    e.description += response + "\n"
                if len(e.description) != 0:
                    embeds.append(pages.Page(embeds=[question_embed, e]))
                if len(embeds) == 0:
                    embeds.append(
                        [
                            question_embed,
                            await ef.general(
                                "There Are No Responses To This Question",
                                message="This Question Was Optional And No One Answered It!",
                            ),
                        ]
                    )
                page_groups.append(
                    pages.PageGroup(label=question.title, description=question.description, pages=embeds)
                )

            pgn = pages.Paginator(pages=page_groups, show_menu=True, timeout=840)
            await pgn.respond(ctx.interaction, ephemeral=True)

        elif grouped == "1":
            sql = """SELECT r.response_num, r.id
            FROM surveys.responses AS r 
            WHERE r.template_id = $1;"""
            db_responses = await db.fetch(sql, template._id)

            response_map = defaultdict(list)
            for response in db_responses:
                response_map[(response["id"], response["response_num"])] = [
                    x for x in responses if x["response"] == response["id"]
                ]

            question_map = {q._id: q for q in questions}

            page_groups = []
            for n, group in enumerate(sorted(response_map.keys())):
                response_embed = discord.Embed(title="Response ID", description=group[0])
                e = discord.Embed(title="Responses", description="")
                embeds = []
                for response in sorted(response_map[group], key=lambda x: question_map[x["question"]].position):
                    question = question_map[response["question"]]
                    r = await question.view_response(response)
                    if len(r) == 0:
                        continue
                    response_text = f"**Question {question.position + 1}:** {await question.short_display()}"
                    response_text += "\n- " + discord.utils.escape_markdown(r)
                    if len(e.description) != 0 and len(e) + len(response_text) > 1024:
                        embeds.append(pages.Page(embeds=[response_embed, e]))
                        e = discord.Embed(title="Responses", description="")
                    e.description += response_text + "\n"
                if len(e.description) != 0:
                    embeds.append(pages.Page(embeds=[response_embed, e]))
                if len(embeds) == 0:
                    # If the survey only has option questions and all questions were skipped
                    continue
                page_groups.append(pages.PageGroup(label=f"Response {n + 1}", pages=embeds))

            pgn = pages.Paginator(pages=page_groups, show_menu=True, timeout=840)
            await pgn.respond(ctx.interaction, ephemeral=True)


def setup(bot):
    bot.add_cog(ResultsCog(bot))
