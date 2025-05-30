import discord
from discord import slash_command, Option
from discord.ext import pages

from forms.survey.template import title_autocomplete, get_templates
from questions.survey_question import from_db, SurveyQuestion
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
        sql = """SELECT * FROM surveys.questions WHERE survey_id=$1"""
        questions: list[SurveyQuestion] = [await from_db(row) for row in await db.fetch(sql, template._id)]
        questions.sort(key=lambda x: x.position)

        if grouped == "0":
            response_map = {q._id: [] for q in questions}

            sql = """SELECT response_data, question FROM surveys.question_response
            WHERE question_response.question = ANY($1::int[]);"""
            responses = await db.fetch(sql, [q._id for q in questions])

            if not responses:
                return await ctx.respond(
                    embed=await ef.fail("There Are No Responses To This Survey Yet"),
                    ephemeral=True,
                )

            for response in responses:
                response_map[response["question"]].append(response["response_data"])

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
            sql = """SELECT r.response_num, q.question, q.response_data, r.id
            FROM surveys.responses AS r INNER JOIN surveys.question_response AS q ON r.id = q.response 
            WHERE r.template_id = $1;"""
            responses = await db.fetch(sql, template._id)

            if not responses:
                return await ctx.respond(
                    embed=await ef.fail("There Are No Responses To This Survey Yet"),
                    ephemeral=True,
                )

            response_map = {}
            for response in responses:
                response_map.setdefault((response["id"], response["response_num"]), []).append(
                    (response["question"], response["response_data"])
                )

            question_map = {q._id: q for q in questions}

            page_groups = []
            for n, group in enumerate(sorted(response_map.keys())):
                response_embed = discord.Embed(title="Response ID", description=group[0])
                e = discord.Embed(title="Responses", description="")
                embeds = []
                for response in sorted(response_map[group], key=lambda x: question_map[x[0]].position):
                    question = question_map[response[0]]
                    r = await question.view_response(response[1])
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
