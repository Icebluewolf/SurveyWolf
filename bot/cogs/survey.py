import datetime
import discord
from discord import slash_command, Option
from datetime import timedelta
from bot.utils.timers import Timer
from discord.ext import tasks, pages
from bot.utils.database import database as db
from bot.utils import embed_factory as ef

MAX_QUESTION_LENGTH = 45
TF_to_YN = {True: "Yes", False: "No"}


def toggle_button(state: bool):
    state = not state
    options = {True: [discord.ButtonStyle.green, "✅"], False: [discord.ButtonStyle.grey, "❌"]}
    return state, options[state][0], options[state][1]


class Wizard(discord.ui.View):
    def __init__(self, embed, user, name):
        # Question Text, Type, Required, Position
        self.questions: list[dict] = []
        self.anonymous: bool = True
        self.all_required: bool = False
        self.edit_responses: bool = False
        self.num_entries: int = 1
        self.time_limit: timedelta | None = None
        self.tnum_entries: int | None = None
        self.name: str = name
        self.embed = embed
        self.user_id = user
        super().__init__(timeout=900)

    @discord.ui.button(label="Set Questions", style=discord.ButtonStyle.primary)
    async def set_questions(self, button, interaction):
        return await interaction.response.send_modal(SetQuestions(self, self.embed))

    @discord.ui.button(label="Anonymous", style=discord.ButtonStyle.green, emoji="✅")
    async def anon_toggle(self, button, interaction):
        self.anonymous, button.style, button.emoji = toggle_button(self.anonymous)
        t = self.embed.fields[1].value.split("\n")
        t[0] = f"Anonymous: {TF_to_YN[self.anonymous]}"
        self.embed.set_field_at(1, name="User Settings", value="\n".join(t))
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label="All Required", style=discord.ButtonStyle.grey, emoji="❌")
    async def req_toggle(self, button, interaction):
        self.all_required, button.style, button.emoji = toggle_button(self.all_required)
        t = self.embed.fields[2].value.split("\n")
        t[0] = f"All Questions Required: {TF_to_YN[self.all_required]}"
        self.embed.set_field_at(2, name="Survey Settings", value="\n".join(t))
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label="Edit Responses", style=discord.ButtonStyle.grey, emoji="❌")
    async def edit_toggle(self, button, interaction):
        self.edit_responses, button.style, button.emoji = toggle_button(self.edit_responses)
        t = self.embed.fields[1].value.split("\n")
        t[2] = f"Edit Responses: {TF_to_YN[self.edit_responses]}"
        self.embed.set_field_at(1, name="User Settings", value="\n".join(t))
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label="Set Other Settings", style=discord.ButtonStyle.primary)
    async def set_misc(self, button, interaction):
        return await interaction.response.send_modal(SetSettings(self, self.embed))

    @discord.ui.button(label="Save And Exit", style=discord.ButtonStyle.green)
    async def save(self, button, interaction):
        await interaction.response.defer()
        if not self.questions:
            return await interaction.response.send_message("Please Set At Least One Question", ephemeral=True)
        sql = """INSERT INTO guild_surveys (guild_id, anonymous, editable, entries_per, total_entries, time_limit, name)
        VALUES ($1, $2, $3, $4, $5, $6, $7);"""
        await db.execute(
            sql,
            interaction.guild.id,
            self.anonymous,
            self.edit_responses,
            self.num_entries,
            self.tnum_entries,
            self.time_limit,
            self.name,
        )
        sql = """INSERT INTO questions (survey_id, text, type, position) SELECT currval('guild_surveys_id_seq'),
                unnest($1::varchar[]), unnest($2::smallint[]), unnest($3::integer[]);"""
        await db.execute(
            sql,
            [x["text"] for x in self.questions],
            [x["type"] for x in self.questions],
            [x["position"] for x in self.questions],
        )
        self.disable_all_items()
        self.stop()
        return await interaction.followup.send("The Survey Was Saved", view=self, embed=self.embed)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "You Did Not Start This Wizard. Use `/create` To Get Started", ephemeral=True
        )

    async def on_timeout(self) -> None:
        self.disable_all_items()


class SetSettings(discord.ui.Modal):
    def __init__(self, wizard: Wizard, embed, *args, **kwargs) -> None:
        self.wiz = wizard
        self.embed = embed
        super().__init__(title="Set Other Settings", *args, **kwargs)

        self.add_item(
            discord.ui.InputText(
                label="Number Of Entries Per Person",
                required=False,
                placeholder='The Default Value For "Number Of Entries Per Person" Is 1',
                value=str(self.wiz.num_entries or 1),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Time Limit",
                required=False,
                placeholder='The Default Value For "Time Limit" Is No Time Limit',
                value=str(self.wiz.time_limit.days) if self.wiz.time_limit else "None",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Total Number Of Entries",
                required=False,
                placeholder='The Default Value For "Total Number Of Entries" Is No Limit',
                value=str(self.wiz.tnum_entries),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Validate Inputs
        errors = []
        t = self.embed.fields[1].value.split("\n")
        # Num Entries
        if self.children[0].value.lower() == "none" or self.children[0].value == "":
            self.wiz.num_entries = 1
            t[1] = f"Number Of Entries Per Person: 1"
        else:
            try:
                v = int(self.children[0].value)
                if v < 1 or v > 20:
                    errors.append("Number Of Entries Per Person Must Be 1 Through 20")
                else:
                    self.wiz.num_entries = v
                    t[1] = f"Number Of Entries Per Person: {v}"
            except ValueError:
                errors.append(
                    "Number Of Entries Per Person Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )
        self.embed.set_field_at(1, name="User Settings", value="\n".join(t))

        # Time Limit
        t = self.embed.fields[2].value.split("\n")
        if self.children[1].value.lower() == "none" or self.children[1].value == "":
            self.wiz.time_limit = None
            t[1] = "Time Limit: None"
        elif Timer.str_time(self.children[1].value).seconds == 0:
            errors.append(
                """You Entered A Value For Time But It Was Not Valid. The Format For Time Is `0s0m0h0d0w`. 
            You Can Put These In Any Order And Leave Out Any Unused Values."""
            )
        else:
            self.wiz.time_limit = Timer.str_time(self.children[1].value)
            t[1] = f"Time Limit: {self.children[1].value}"

        # Total Num Entries
        if self.children[2].value.lower() == "none" or self.children[2].value == "":
            self.wiz.tnum_entries = None
            t[2] = f"Total Number Of Entries: None"
        else:
            try:
                v = int(self.children[2].value)
                if v < 1 or v > 20000:
                    errors.append("Total Number Of Entries Must Be 1 Through 20,000")
                else:
                    if v == 0:
                        v = "None"
                    t[2] = f"Total Number Of Entries: {v}"
            except ValueError:
                errors.append(
                    "Total Number Of Entries Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )
        self.embed.set_field_at(2, name="Survey Settings", value="\n".join(t))

        await interaction.response.edit_message(embed=self.embed, view=self.wiz)
        if errors:
            em = discord.Embed(
                title="Some Settings Failed",
                description="Below Are The Errors Of The Settings That Were Not Inputted Correctly. If "
                "There Is Not An Error The Setting Was Successfully Set.",
                color=0xD33033,
            )
            em.add_field(name="Errors", value="\n".join(errors))
            await interaction.followup.send(embed=em, ephemeral=True)


class SetQuestions(discord.ui.Modal):
    def __init__(self, wizard: Wizard, embed, *args, **kwargs) -> None:
        self.wiz = wizard
        self.embed = embed
        super().__init__(title="Set Questions", *args, **kwargs)

        for i in range(5):
            try:
                v = self.wiz.questions[i]["text"]
            except IndexError:
                v = None
            self.add_item(
                discord.ui.InputText(
                    label=f"Enter Question {i + 1}", required=False, max_length=MAX_QUESTION_LENGTH, value=v
                )
            )

    async def callback(self, interaction: discord.Interaction):
        self.wiz.questions = []
        for n, i in enumerate(self.children):
            if i.value != "":
                self.wiz.questions.append({"text": i.value, "type": 0, "required": True, "position": i.row})
        self.embed.set_field_at(0, name="Questions", value="\n".join([x["text"] for x in self.wiz.questions]))
        await interaction.response.edit_message(view=self.wiz, embed=self.embed)


class SurveyModel(discord.ui.Modal):
    qtypes = {0: discord.ui.InputText}

    def __init__(self, survey_id: int, title: str, questions):
        super().__init__(title=title, timeout=1800)

        self.questions = questions
        self.survey = survey_id

        for question in self.questions:
            self.add_item(
                SurveyModel.qtypes[question["type"]](
                    label=question["text"],
                    custom_id=str(question["id"]),
                    row=question["position"],
                    max_length=255,
                )
            )

    async def callback(self, interaction: discord.Interaction):
        sql = """INSERT INTO responses (user_id, active_survey_id, question_id, response, response_num) 
        VALUES ($1, $2, unnest($3::integer[]), unnest($4::varchar[]), 
        (SELECT coalesce(max(response_num), 0) + 1 FROM responses 
        WHERE user_id=$1 and active_survey_id = $2));"""
        await db.execute(
            sql,
            interaction.user.id,
            self.survey,
            [int(x.custom_id) for x in self.children],
            [x.value for x in self.children],
        )
        await interaction.response.send_message("You Completed The Survey!", ephemeral=True)


class SurveyButton(discord.ui.View):
    def __init__(self, survey, custom_id: str, end_time: datetime.datetime = None, **kwargs):
        self.template_id: int = survey["template_id"]
        self.guild_id: int = survey["guild_id"]
        self.anon: int = survey["anonymous"]
        self.editable: bool = survey["editable"]
        self.entries_per: int = survey["entries_per"]
        self.total_entries: int = survey["total_entries"]
        self.name: str = survey["name"]
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
        print(self.end_time)
        print(datetime.datetime.now())
        if self.end_time and self.end_time < datetime.datetime.now():
            await interaction.response.send_message(
                embed=await ef.fail("This Survey Is Now Closed As The End Date Has Been Reached"),
                ephemeral=True,
            )
            return await self._close_survey()

        sql = """SELECT DISTINCT max(response_num) FROM responses 
        WHERE user_id=$2 and active_survey_id = $1;"""
        times_taken = await db.fetch(sql, int(self.custom_id), interaction.user.id)
        print(times_taken)

        if self.entries_per is not None and times_taken[0][0] is not None:
            if times_taken[0][0] >= self.entries_per:
                return await interaction.response.send_message(
                    embed=await ef.fail("You Have Taken This Survey The Maximum Number Of Times Allowed"),
                    ephemeral=True,
                )

        # sql = "SELECT DISTINCT ON () sum(response_num) FROM responses WHERE question_id=$1;"
        # total_responses = await db.fetch(sql, self.sid)
        total_responses = [[0]]

        if self.total_entries is not None and total_responses[0][0] is not None:
            if total_responses[0][0] >= self.total_entries:
                self.disable_all_items()
                self.stop()
                return await interaction.response.send_message(
                    embed=await ef.fail(
                        "This Survey Is Now Closed As The Maximum Number Of Responses Has Been Reached."
                    ),
                    ephemeral=True,
                )

        sql = "SELECT text, type, position, id FROM questions WHERE survey_id=$1;"
        print(self.template_id)
        await interaction.response.send_modal(
            SurveyModel(int(self.custom_id), self.name, await db.fetch(sql, self.template_id))
        )

    async def _close_survey(self):
        e = await ef.general(title=self.name, message="The Survey Has Been Closed")
        self.disable_all_items()
        await self.message.edit(embed=e, view=self)
        self.stop()

    async def close_survey(self, message: discord.Message):
        self.message = message
        await self._close_survey()


class Survey(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.survey_name_cache: {[str, int]} = {}

    @slash_command(description="Opens The Form Creation Wizard")
    @discord.default_permissions(manage_guild=True)
    async def create(
        self, ctx, name: discord.Option(str, description="The Name For This Survey", max_length=64, required=True)
    ):
        em = discord.Embed(
            title="Survey Creation Wizard",
            description="""Edit the settings for your survey. Any option that is not filled will 
                           default to the displayed value or none.""",
            fields=[
                discord.EmbedField(name="Questions", value="No Questions"),
                discord.EmbedField(
                    name="User Settings", value="Anonymous: Yes\nNumber Of Entries " "Per Person: 1\nEdit Responses: No"
                ),
                discord.EmbedField(
                    name="Survey Settings",
                    value="All Questions Required: " "Yes\nTime Limit: None\nTotal " "Number Of Entries: None",
                ),
            ],
        )
        view = Wizard(em, ctx.author.id, name)
        m = await ctx.respond(embed=em, view=view)
        if await view.wait():
            try:
                m.edit(view=view)
            except AttributeError:
                m.message.edit(view=view)
            await ctx.send_followup("Survey Creation Timed Out. Remember Only 15 Minutes Is Given")

    async def get_surveys(self, ctx: discord.AutocompleteContext):
        try:
            results = self.survey_name_cache[ctx.interaction.guild.id]
        except KeyError:
            sql = "SELECT name FROM guild_surveys WHERE guild_id = $1;"
            results = [x["name"] for x in await db.fetch(sql, ctx.interaction.guild.id)]
            results = results or ["No Surveys Found. Use /create To Make One"]
            self.survey_name_cache[ctx.interaction.guild.id] = results
        if results == ["No Surveys Found. Use /create To Make One"]:
            return results
        else:
            return [name for name in results if name.lower().startswith(ctx.value.lower())]

    @tasks.loop(minutes=3)
    async def _clear_cache(self):
        self.survey_name_cache = {}

    @slash_command(description="Opens The Survey For Submissions")
    @discord.default_permissions(manage_guild=True)
    async def attach(
        self,
        ctx,
        name: Option(str, name="survey", description="The Survey To Attach", autocomplete=get_surveys),
        message: Option(str, name="message", description='The Message Above The "Take Survey" Button', required=False),
        time: Option(
            str,
            name="time_override",
            description="Overrides The Default Time Set In The Survey Template",
            required=False,
            default="",
        ),
    ):
        if name == "No Surveys Found. Use /create To Make One":
            ctx.send(embed=await ef.fail("I Told You You Needed To Use /create >:("), ephemeral=True)

        sql = """SELECT id AS template_id, guild_id, anonymous, editable, entries_per, total_entries, time_limit, name 
        FROM guild_surveys WHERE guild_id = $1 AND name = $2;"""
        survey = await db.fetch(sql, ctx.guild.id, name)

        if not survey:
            return await ctx.send(
                embed=await ef.fail("There Is No Survey With This Name. Try Selecting One Of The Provided Options."),
                ephemeral=True,
            )
        end = Timer.str_time(time)
        end = end if end.total_seconds() != 0 else survey[0]["time_limit"]
        if end is not None:
            end = datetime.datetime.now() + end
        sql = "INSERT INTO active_guild_surveys (end_date, template_id) VALUES ($1, $2) RETURNING id;"
        button_id = await db.fetch(sql, end, survey[0]["template_id"])

        e = await ef.general(name, message)
        return await ctx.respond(
            content="", embed=e, view=SurveyButton(survey[0], str(button_id[0]["id"]), end_time=end)
        )

    @slash_command(description="Close A Survey Before The Time Limit Or Max Amount Of Entries Has Been Reached")
    @discord.default_permissions(manage_guild=True)
    async def close(
        self,
        ctx,
        message_id: Option(
            str,
            name="message",
            description="The Message ID OR Link To The Message That Should Be Closed",
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
        print(self.bot.persistent_views)
        if not isinstance(view, SurveyButton):
            return await ctx.respond(embed=await ef.fail("That Is Not A Message For A Survey"), ephemeral=True)
        await view.close_survey(message)
        return await ctx.respond(embed=await ef.success("The Survey Was Closed!"), ephemeral=True)

    @slash_command(description="View The Results And Responses Of A Survey")
    @discord.default_permissions(manage_guild=True)
    async def results(
        self,
        ctx,
        survey: Option(str, description="The Survey To See The Results Of", autocomplete=get_surveys),
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
        if survey == "No Surveys Found. Use /create To Make One":
            return await ctx.send(embed=await ef.fail("I Told You You Needed To Use /create >:("), ephemeral=True)

        sql = """SELECT id FROM guild_surveys WHERE guild_id = $1 AND name = $2;"""
        survey_row = await db.fetch(sql, ctx.guild.id, survey)

        if not survey_row:
            return await ctx.send(
                embed=await ef.fail("There Is No Survey With This Name. Try Selecting One Of The Provided Options."),
                ephemeral=True,
            )

        # Get Questions
        sql = """SELECT id, type, text, position FROM questions WHERE survey_id=$1"""
        questions = await db.fetch(sql, survey_row[0]["id"])

        questions = {q["id"]: (q["position"], q["type"], q["text"]) for q in questions}
        survey_description = discord.Embed(title=f"Results For {survey}",
                                           description="\n".join([f"{q[0]}. {q[2]}" for q in questions.values()]))

        if grouped == "0":
            sql = """SELECT user_id, question_id, response FROM responses 
            WHERE question_id IN (SELECT id FROM questions WHERE survey_id=$1)
            ORDER BY question_id;"""
        elif grouped == "1":
            sql = """SELECT user_id, question_id, response FROM responses 
            WHERE question_id IN (SELECT id FROM questions WHERE survey_id=$1)
            ORDER BY active_survey_id, question_id;"""
        elif grouped == "2":
            sql = """SELECT user_id, question_id, response FROM responses 
            WHERE active_survey_id IN (SELECT id FROM active_guild_surveys WHERE template_id=$1)
            ORDER BY user_id, question_id;"""
        else:
            return
        responses = await db.fetch(sql, survey_row[0]["id"])

        # Splits The Responses Into Easily Readable Chunks.
        embeds = []
        e = discord.Embed()
        current_length = 0
        for response in responses:
            if current_length + len(response["response"]) > 1024 or len(e.fields) >= 8:
                embeds.append([survey_description, e])
                e = discord.Embed()
                current_length = 0
            e.add_field(name=f"Question {questions[response['question_id']][0]}",
                        value=f"From <@{response['user_id']}>\n{response['response']}",
                        inline=False,
                        )
            current_length += len(response["response"])
        if e.fields:
            embeds.append([survey_description, e])

        pgn = pages.Paginator(pages=embeds)
        await pgn.respond(ctx.interaction, ephemeral=True)

    @discord.Cog.listener()
    async def on_ready(self):
        # Load persistent buttons
        sql = """SELECT ags.id AS ags_id, ags.end_date, ags.template_id, 
         gs.id AS t_id, gs.time_limit, gs.total_entries, gs.entries_per, gs.editable, gs.anonymous, gs.name, gs.guild_id 
         FROM active_guild_surveys ags LEFT JOIN guild_surveys gs on gs.id = ags.template_id;"""
        active_surveys = await db.fetch(sql)

        for row in active_surveys:
            time = row["end_date"]
            if time is not None and time <= datetime.datetime.now():
                # In The Future An Extra 30 Minutes Could Be Added To Survey That Ended When The Bot Was Offline

                continue
            view = SurveyButton(row, custom_id=str(row["ags_id"]), end_time=time)
            print(row)
            self.bot.add_view(view)


def setup(bot):
    bot.add_cog(Survey(bot))
