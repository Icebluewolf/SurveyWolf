import datetime
import discord
from discord import slash_command, Option
from utils.timers import Timer
from utils.database import database as db
from utils import embed_factory as ef
from utils.db_classes import BaseQuestion, Survey, ActiveSurvey, QuestionType, gather_questions
from cogs.survey.old_survey import survey_name_autocomplete, get_survey, _clear_cache

class ActiveResponse:
    def __init__(self, interaction: discord.Interaction, survey: Survey, questions: list[BaseQuestion], responses: \
        list[str]):
        self.user = interaction.user
        self.interaction = interaction
        self.survey = survey
        self.questions = questions
        self.question_index = 0
        self.responses = responses

        self.current_questions = []


    async def start(self):
        await self.send_next_question(interaction=self.interaction)

    async def send_next_question(self, interaction: discord.Interaction):

        if self.question_index + 1 == len(self.questions):
            return await self.finish_survey()

        self.current_questions = []
        if self.questions[self.question_index].q_type == QuestionType.text:
            # Get Leading Text Response Questions With A Limit Of 5
            for n, question in enumerate(self.questions[self.question_index:]):
                if n < 5 and question.q_type == 0:
                    self.current_questions.append(question)
                else:
                    break
            self.question_index += len(self.current_questions)
            await interaction.response.send_modal(TextResponse(self))

        elif self.questions[self.question_index].q_type == QuestionType.multiple_choice:
            self.current_questions = [self.questions[self.question_index]]
            self.question_index += 1
            options = [f"{chr(n+65)}. {text}" for n, text in enumerate(self.current_questions[0].options)]
            embed = ef.general(self.current_questions[0].text, message="\n".join(options))
            view = MultipleChoiceResponse(self, options)
            await interaction.respond(embed=embed, view=view, ephemeral=True)

    async def add_responses(self, new_responses: str | list[str], interaction: discord.Interaction):
        self.interaction = interaction

        if isinstance(new_responses, str):
            current_responses = [new_responses]

        self.responses.extend(new_responses)
        await self.send_next_question(interaction=self.interaction)

    async def finish_survey(self):
        sql = """INSERT INTO surveys.responses (user_id, active_survey_id, question_id, response, response_num) 
                VALUES ($1, $2, unnest($3::integer[]), unnest($4::varchar[]), 
                (SELECT coalesce(max(response_num), 0) + 1 FROM surveys.responses 
                WHERE user_id=$1 and active_survey_id = $2));"""
        await db.execute(
            sql,
            self.user.id,
            self.survey.id,
            [int(x.q_id) for x in self.questions],
            self.responses,
        )

        await self.interaction.respond(
            embed=ef.success("You Completed The Survey And Your Responses Have Been Recorded!")
        )

class TextResponse(discord.ui.Modal):
    qtypes = {0: discord.ui.InputText}

    def __init__(self, active_response: ActiveResponse):
        super().__init__(title=active_response.survey.name, timeout=1800)
        self.active_response = active_response

        for question in self.active_response.current_questions:
            self.add_item(
                TextResponse.qtypes[question.q_type](
                    label=question.text,
                    row=question.pos,
                    max_length=255,
                    required=question.required,
                    custom_id=str(question.qid),
                )
            )

    async def callback(self, interaction: discord.Interaction):
        await self.active_response.add_responses([x.value for x in self.children], interaction)

class MultipleChoiceResponse(discord.ui.View):
    # TODO: Make This Take Its Own Subclass For A Multiple Choice Question
    def __init__(self, active_response: ActiveResponse, formatted_options):
        super().__init__(timeout=300)
        self.active_response = active_response
        self.current_choice = None

        for option in formatted_options:
            button = discord.ui.Button(style=discord.ButtonStyle.blurple, label=option[:80])
            self.add_item(button)

    async def callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.style = discord.ButtonStyle.green
        button.disabled = True
        self.current_choice = button.label[0]
        await interaction.response.edit(view=self)


    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green, row=4)
    async def submit(self, button, interaction: discord.Interaction):
        await self.active_response.add_responses(str(ord(self.current_choice) - 65), interaction)
        await interaction.followup.delete_original_response()

class SurveyButton(discord.ui.View):
    def __init__(self, survey: Survey, custom_id: str, end_time: datetime.datetime = None, **kwargs):
        self.template = survey
        self.custom_id: str = custom_id
        self.end_time: datetime.datetime = end_time
        super().__init__(**kwargs, timeout=None)

        # To Add The Custom ID The Button Needs To Be Created Manually
        start_button = discord.ui.Button(label="Take Survey", style=discord.ButtonStyle.primary, custom_id=custom_id)
        start_button.callback = self.start_survey
        self.add_item(start_button)

    def is_persistent(self) -> bool:
        return all(item.is_persistent() for item in self.children)

    async def start_survey(self, interaction):
        if self.message is None:
            self._message = interaction.message
        if self.end_time and self.end_time < datetime.datetime.now():
            await interaction.response.send_message(
                embed=await ef.fail("This Survey Is Now Closed As The End Date Has Been Reached"),
                ephemeral=True,
            )
            return await self._close_survey()

        sql = """SELECT DISTINCT max(response_num) FROM surveys.responses 
        WHERE user_id=$2 and active_survey_id = $1;"""
        times_taken = await db.fetch(sql, int(self.custom_id), interaction.user.id)

        if self.template.entries_per is not None and times_taken[0][0] is not None:
            if times_taken[0][0] >= self.template.entries_per:
                return await interaction.response.send_message(
                    embed=await ef.fail("You Have Taken This Survey The Maximum Number Of Times Allowed"),
                    ephemeral=True,
                )

        # sql = "SELECT DISTINCT ON () sum(response_num) FROM surveys.responses WHERE question_id=$1;"
        # total_responses = await db.fetch(sql, self.sid)
        total_responses = [[0]]

        if self.template.total_entries is not None and total_responses[0][0] is not None:
            if total_responses[0][0] >= self.template.total_entries:
                self.disable_all_items()
                self.stop()
                return await interaction.response.send_message(
                    embed=await ef.fail(
                        "This Survey Is Now Closed As The Maximum Number Of Responses Has Been Reached."
                    ),
                    ephemeral=True,
                )

        sql = """SELECT text, type, position, required, id, options, min_choices, max_choices FROM surveys.questions 
              WHERE survey_id=$1;"""
        questions = await gather_questions(await db.fetch(sql, self.template.id))

        ar = ActiveResponse(interaction, self.template, questions, [])
        await ar.start()

    async def _close_survey(self):
        e = await ef.general(title=self.template.name, message="The Survey Has Been Closed")
        self.disable_all_items()
        await self.message.edit(embed=e, view=self)
        self.stop()

    async def close_survey(self, message: discord.Message):
        self.message = message
        await self._close_survey()


class ResponseCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
    @slash_command(description="Opens The Survey For Submissions")
    @discord.default_permissions(manage_guild=True)
    async def attach(
        self,
        ctx,
        name: Option(
            str,
            name="survey",
            description="The Survey To Attach",
            autocomplete=survey_name_autocomplete,
        ),
        message: Option(
            str,
            name="message",
            description='The Message Above The "Take Survey" Button',
            required=False,
        ),
        time: Option(
            str,
            name="time_override",
            description="Overrides The Default Time Set In The Survey Template",
            required=False,
            default="",
        ),
    ):
        survey = await get_survey(name, ctx)
        if survey is None:
            return
        end = Timer.str_time(time)
        end = end if end.total_seconds() != 0 else survey.time_limit
        if end is not None:
            end = datetime.datetime.now() + end
        sql = "INSERT INTO surveys.active_guild_surveys (end_date, template_id) VALUES ($1, $2) RETURNING id;"
        button_id = await db.fetch(sql, end, survey.id)

        e = await ef.general(name, message)
        return await ctx.respond(
            content="",
            embed=e,
            view=SurveyButton(survey, str(button_id[0]["id"]), end_time=end),
        )

    @slash_command(description="Close A Survey Before The Time Limit Or Max Amount Of Entries Has Been Reached")
    @discord.default_permissions(manage_guild=True)
    async def close(
        self,
        ctx,
        message_id: Option(
            str,
            name="message",
            description="The Message Link Or ID To The Survey That Should Be Closed",
        ),
    ):
        if message_id.isdigit():
            message = await ctx.channel.fetch_message(message_id)
        else:
            message = await ctx.channel.fetch_message(message_id.split("/")[-1])

        if message is None:
            return await ctx.respond(
                embed=await ef.fail(
                    "I Could Not Find A Message With That ID/Link In This Channel. Make Sure You Run This Command In "
                    "The Channel That This Survey Is In "
                ),
                ephemeral=True,
            )
        mview = discord.ui.View.from_message(message)
        view: SurveyButton = discord.utils.find(
            lambda v: v.children[0].custom_id == mview.children[0].custom_id,
            self.bot.persistent_views,
        )
        if not isinstance(view, SurveyButton):
            return await ctx.respond(
                embed=await ef.fail("That Is Not A Message For A Survey"),
                ephemeral=True,
            )
        await view.close_survey(message)
        return await ctx.respond(embed=await ef.success("The Survey Was Closed!"), ephemeral=True)

    @discord.Cog.listener()
    async def on_ready(self):
        # Load persistent buttons
        sql = """SELECT ags.id AS ags_id, ags.end_date, ags.template_id, 
             gs.id AS t_id, gs.time_limit, gs.total_entries, gs.entries_per, gs.editable, gs.anonymous, gs.name, gs.guild_id 
             FROM surveys.active_guild_surveys ags LEFT JOIN surveys.guild_surveys gs on gs.id = ags.template_id;"""
        active_surveys = await db.fetch(sql)

        for row in active_surveys:
            active_s = await ActiveSurvey.from_db_row(row)
            time = active_s.end_date
            if time is not None and time <= datetime.datetime.now():
                # In The Future An Extra 30 Minutes Could Be Added To Survey That Ended When The Bot Was Offline

                continue
            view = SurveyButton(await active_s.get_template(), custom_id=str(active_s.id), end_time=time)
            self.bot.add_view(view)

        _clear_cache.start()

def setup(bot):
    bot.add_cog(ResponseCog(bot))