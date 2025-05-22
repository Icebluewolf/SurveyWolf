import discord
from discord import slash_command, Option, Interaction
from discord.ext import pages

from forms.survey.template import title_autocomplete, get_templates
from questions.survey_question import from_db, SurveyQuestion
from utils.database import database as db
from utils import component_factory as cf


class OverflowButton(discord.ui.Button):
    def __init__(self, text: str):
        super().__init__(label="Click To See The Full Text")
        self.text = text

    async def callback(self, interaction: Interaction):
        v = discord.ui.View()
        v.add_item(discord.ui.Container(discord.ui.TextDisplay(self.text)))
        await interaction.respond(view=v, ephemeral=True)


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
            return await ctx.respond(view=discord.ui.View(await cf.fail(f"No Survey Named `{name}` Found"), timeout=0), ephemeral=True)

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
                    view=discord.ui.View(await cf.fail("There Are No Responses To This Survey Yet"), timeout=0),
                    ephemeral=True,
                )

            for response in responses:
                response_map[response["question"]].append(response["response_data"])

            page_groups = []
            for question in questions:
                response_component = await question.display()
                c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                pending_response_text = ""
                containers = []
                for response in response_map[question._id]:
                    r = await question.view_response(response)
                    if len(r) == 0:
                        continue
                    response_text = "- " + discord.utils.escape_markdown(r) + "\n"
                    # if len(c.items) > 2 and len(c.copy_text()) + len(response_text) > 1024:
                    #     containers.append([response_component, c])
                    #     c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                    # c.add_text(response_text)
                    # If there is space for the question add it to the pending data and continue before adding to view
                    if len(response_component.copy_text()) + len(pending_response_text) + len(response_text) <= 1024:
                        pending_response_text += response_text
                        continue
                    elif len(response_text) > 4000:
                        # If the response cant fit in a single message add any existing data
                        if pending_response_text:
                            c.add_text(pending_response_text)
                            containers.append([response_component, c])
                            c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                        # Create the overflow UI
                        overwrite = "\n..."
                        section = discord.ui.Section(
                            discord.ui.TextDisplay("The Response Is To Long To Fit In One Message"),
                            accessory=OverflowButton(r),
                        )
                        response_text = response_text[:3999 - len(overwrite) - len(c.copy_text()) - len(
                            section.copy_text()) - len(response_component.copy_text())] + overwrite
                        c.add_text(response_text)
                        c.add_separator()
                        c.add_item(section)
                        response_text = ""
                    else:
                        # The text should be split before adding this response
                        c.add_text(pending_response_text)

                    # This only occurs if the text should be split, it will add to the view and create new components
                    pending_response_text = response_text
                    containers.append([response_component, c])
                    c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                if pending_response_text:
                    c.add_text(pending_response_text)
                    containers.append([response_component, c])
                if len(containers) == 0:
                    containers.append(
                        [
                            response_component,
                            discord.ui.Container(
                                discord.ui.TextDisplay(
                                    """
                                    ### There Are No Responses To This Question
                                    This Question Was Optional And No One Answered It!
                                    """
                                )
                            ),
                        ]
                    )
                custom_views = [pages.Page(custom_view=discord.ui.View(*container)) for container in containers]
                page_groups.append(
                    pages.PageGroup(label=question.title, description=question.description, pages=custom_views, default_button_row=3)
                )

            pgn = pages.Paginator(pages=page_groups, show_menu=True, timeout=840, default_button_row=3)
            await pgn.respond(ctx.interaction, ephemeral=True)

        elif grouped == "1":
            sql = """SELECT r.response_num, q.question, q.response_data, r.id
            FROM surveys.responses AS r INNER JOIN surveys.question_response AS q ON r.id = q.response 
            WHERE r.template_id = $1;"""
            responses = await db.fetch(sql, template._id)

            if not responses:
                return await ctx.respond(
                    view=discord.ui.View(await cf.fail("There Are No Responses To This Survey Yet"), timeout=0),
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
                response_component = discord.ui.Container(discord.ui.TextDisplay("### Response ID\n" + str(group[0])))
                c = discord.ui.Container(
                    discord.ui.TextDisplay("## Responses"),
                    discord.ui.Separator(),
                )
                views = []
                view = discord.ui.View(response_component, c)
                pending_response_text = ""
                for response in sorted(response_map[group], key=lambda x: question_map[x[0]].position):
                    question = question_map[response[0]]
                    r = await question.view_response(response[1])
                    if len(r) == 0:
                        continue

                    response_text = f"### Question {question.position + 1}: {await question.short_display()}"
                    response_text += "\n    " + discord.utils.escape_markdown(r) + "\n"

                    # If there is space for the question add it to the pending data and continue before adding to view
                    if len(view.copy_text()) + len(pending_response_text) + len(response_text) <= 1024:
                        pending_response_text += response_text
                        continue
                    elif len(response_text) > 4000:
                        # If the response cant fit in a single message add any existing data
                        if pending_response_text:
                            c.add_text(pending_response_text)
                            views.append(view)
                            c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                            view = discord.ui.View(response_component, c)
                        # Create the overflow UI
                        overwrite = "\n..."
                        section = discord.ui.Section(
                            discord.ui.TextDisplay("The Response Is To Long To Fit In One Message"),
                            accessory=OverflowButton(r),
                        )
                        response_text = response_text[:3999 - len(overwrite) - len(view.copy_text()) - len(section.copy_text())] + overwrite
                        c.add_text(response_text)
                        c.add_separator()
                        c.add_item(section)
                        response_text = ""
                    elif pending_response_text:
                        # The text should be split before adding this response
                        c.add_text(pending_response_text)

                    # This only occurs if the text should be split, it will add to the view and create new components
                    pending_response_text = response_text
                    views.append(view)
                    c = discord.ui.Container(discord.ui.TextDisplay("## Responses"), discord.ui.Separator())
                    view = discord.ui.View(response_component, c)

                # If there are leftover responses not yet added to the view
                if len(pending_response_text) > 0:
                    c.add_text(pending_response_text)
                    views.append(view)
                if len(views) == 0:
                    # If the survey only has optional questions and all questions were skipped
                    continue

                custom_views = [pages.Page(custom_view=view) for view in views]
                page_groups.append(pages.PageGroup(label=f"Response {n + 1}", pages=custom_views, default_button_row=3))

            pgn = pages.Paginator(pages=page_groups, show_menu=True, timeout=840, default_button_row=3)
            await pgn.respond(ctx.interaction, ephemeral=True)


def setup(bot):
    bot.add_cog(ResultsCog(bot))
