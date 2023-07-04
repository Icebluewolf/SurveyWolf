import datetime
import discord
from discord import slash_command, Option
from datetime import timedelta
from utils.timers import Timer
from discord.ext import tasks, pages
from utils.database import database as db
from utils import embed_factory as ef

MAX_QUESTION_LENGTH = 45
TF_to_YN = {True: "Yes", False: "No"}

QUESTION_TYPES = {0: "Text"}


def toggle_button(state: bool):
    state = not state
    options = {
        True: [discord.ButtonStyle.green, "✅"],
        False: [discord.ButtonStyle.grey, "❌"],
    }
    return state, options[state][0], options[state][1]


class Wizard(discord.ui.View):
    def __init__(self, em, user, name):
        # Question Text, Type, Required, Position
        self.questions: list[dict] = []
        self.anonymous: bool = True
        self.edit_responses: bool = False
        self.num_entries: int = 1
        self.time_limit: timedelta | None = None
        self.tnum_entries: int | None = None
        self.name: str = name
        self.embed: discord.Embed = em
        self.user_id = user
        super().__init__(timeout=900)

    async def update_embed(self):
        em = discord.Embed(
            title="Survey Creation Wizard",
            description="""Edit the settings for your survey. Any option that is not filled will 
                                   default to the displayed value or none.""",
            fields=[
                discord.EmbedField(name="Survey Name", value=self.name),
                discord.EmbedField(
                    name="Questions",
                    value="\n".join(
                        [
                            f"{n + 1} - " + x["text"]
                            for n, x in enumerate(self.questions)
                        ]
                    )
                    or "No " "Questions",
                    inline=True,
                ),
                discord.EmbedField(
                    name="Required",
                    value="\n".join([str(x["required"]) for x in self.questions]),
                    inline=True,
                ),
                discord.EmbedField(
                    name="Type",
                    value="\n".join(
                        [QUESTION_TYPES[x["type"]] for x in self.questions]
                    ),
                    inline=True,
                ),
                discord.EmbedField(
                    name="User Settings",
                    value=f"""**[WIP]** Anonymous: {'Yes' if self.anonymous else 'No'}
                              Number Of Entries Per Person: {self.num_entries}
                              **[WIP]** Edit Responses: {'Yes' if self.edit_responses else 'No'}""",
                ),
                discord.EmbedField(
                    name="Survey Settings",
                    value=f"""Time Limit: {self.time_limit}
                    Total Number Of Entries: {str(self.tnum_entries) if self.tnum_entries else 'No Limit'}""",
                ),
            ],
        )
        self.embed = em
        await self.message.edit(embed=em, view=self)

    async def insert_question(
        self, position: int, text: str, input_type: int, required: bool
    ):
        self.questions.insert(
            position,
            {
                "text": text,
                "type": input_type,
                "required": required,
                "position": len(self.questions) + 1,
            },
        )

    async def delete_question(self, position: int):
        self.questions.pop(position)

    @discord.ui.button(label="Edit Questions", style=discord.ButtonStyle.primary)
    async def edit_questions(self, button, interaction):
        await interaction.response.send_message(view=EditQuestions(self))

    @discord.ui.button(
        label="[WIP] Anonymous",
        style=discord.ButtonStyle.green,
        emoji="✅",
        disabled=True,
    )
    async def anon_toggle(self, button, interaction):
        self.anonymous, button.style, button.emoji = toggle_button(self.anonymous)
        await self.update_embed()
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(
        label="[WIP] Edit Responses",
        style=discord.ButtonStyle.grey,
        emoji="❌",
        disabled=True,
    )
    async def edit_toggle(self, button, interaction):
        self.edit_responses, button.style, button.emoji = toggle_button(
            self.edit_responses
        )
        await self.update_embed()
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label="Set Other Settings", style=discord.ButtonStyle.primary)
    async def set_misc(self, button, interaction):
        return await interaction.response.send_modal(SetSettings(self))

    @discord.ui.button(label="Save And Exit", style=discord.ButtonStyle.green)
    async def save(self, button, interaction):
        if not self.questions:
            return await interaction.response.send_message(
                "Please Set At Least One Question", ephemeral=True
            )
        await interaction.response.defer()
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
        sql = """INSERT INTO questions (survey_id, text, type, position, required) SELECT currval('guild_surveys_id_seq'),
                unnest($1::varchar[]), unnest($2::smallint[]), unnest($3::integer[]), unnest($4::bool[]);"""
        await db.execute(
            sql,
            [x["text"] for x in self.questions],
            [x["type"] for x in self.questions],
            [x for x in range(len(self.questions))],
            [x["required"] for x in self.questions],
        )
        self.disable_all_items()
        self.stop()
        await interaction.edit_original_response(
            content="The Survey Was Saved", view=self, embed=self.embed
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "You Did Not Start This Wizard. Use `/create` To Get Started",
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.message.edit(view=self)


class SetSettings(discord.ui.Modal):
    def __init__(self, wizard: Wizard, *args, **kwargs) -> None:
        self.wiz = wizard
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
        # Num Entries
        if self.children[0].value.lower() == "none" or self.children[0].value == "":
            self.wiz.num_entries = 1
        else:
            try:
                v = int(self.children[0].value)
                if v < 1 or v > 20:
                    errors.append("Number Of Entries Per Person Must Be 1 Through 20")
                else:
                    self.wiz.num_entries = v
            except ValueError:
                errors.append(
                    "Number Of Entries Per Person Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )

        # Time Limit
        if self.children[1].value.lower() == "none" or self.children[1].value == "":
            self.wiz.time_limit = None
        elif Timer.str_time(self.children[1].value).total_seconds() == 0:
            errors.append(
                """You Entered A Value For Time But It Was Not Valid. The Format For Time Is `0s0m0h0d0w`. 
            You Can Put These In Any Order And Leave Out Any Unused Values."""
            )
        else:
            self.wiz.time_limit = Timer.str_time(self.children[1].value)

        # Total Num Entries
        if self.children[2].value.lower() == "none" or self.children[2].value == "":
            self.wiz.tnum_entries = None
        else:
            try:
                v = int(self.children[2].value)
                if v < 1 or v > 20000:
                    errors.append("Total Number Of Entries Must Be 1 Through 20,000")
                else:
                    if v == 0:
                        self.wiz.tnum_entries = None
                    else:
                        self.wiz.tnum_entries = v
            except ValueError:
                errors.append(
                    "Total Number Of Entries Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )
        await self.wiz.update_embed()
        await interaction.response.edit_message(embed=self.wiz.embed, view=self.wiz)
        if errors:
            em = discord.Embed(
                title="Some Settings Failed",
                description="Below Are The Errors Of The Settings That Were Not Inputted Correctly. If "
                "There Is Not An Error The Setting Was Successfully Set.",
                color=0xD33033,
            )
            em.add_field(name="Errors", value="\n".join(errors))
            await interaction.followup.send(embed=em)


class QuestionSelector(discord.ui.Select):
    def __init__(self, questions: list[dict]):
        super().__init__(placeholder="Select A Question To Edit", row=0)
        self.update(questions)

    def update(self, questions: list[dict], default=None):
        self.options = [
            discord.SelectOption(label=f"{n + 1}. {x['text']}", value=str(n))
            if n != default
            else discord.SelectOption(
                label=f"{n + 1}. {x['text']}", value=str(n), default=True
            )
            for n, x in enumerate(questions)
        ]
        if len(self.options) == 0:
            self.options = [
                discord.SelectOption(
                    label="No Questions Have Been Created Yet", value="-1"
                )
            ]

    async def callback(self, interaction: discord.Interaction):
        if int(self.values[0]) != -1:
            self.view.current_pos = int(self.values[0])
            self.update(self.view.wiz.questions, self.view.current_pos)
            await interaction.response.edit_message(view=self.view)


class EditQuestions(discord.ui.View):
    def __init__(self, wizard: Wizard):
        super().__init__()
        self.wiz = wizard
        self.current_pos = None

        self.selector = QuestionSelector(self.wiz.questions)
        self.add_item(self.selector)

    @discord.ui.button(
        label="Add Question", style=discord.ButtonStyle.green, emoji="➕", row=1
    )
    async def add_question_btn(
        self, button: discord.Button, interaction: discord.Interaction
    ):
        print(self.wiz.questions)
        if len(self.wiz.questions) >= 5:
            return await interaction.response.send_message(
                embed=await ef.fail(
                    "You Cannot Have More Then 5 "
                    "Questions. I Know It Is Dumb But "
                    "There Is Not A Good Way To Get Around It Currently. A Work Around Will Be Added In The Future. Blame Discord"
                ),
                ephemeral=True,
            )
        modal = AddQuestion(self.wiz)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.current_pos = len(self.wiz.questions) - 1
        self.selector.update(self.wiz.questions, default=self.current_pos)
        await self.wiz.update_embed()
        await self.message.edit(view=self)

    @discord.ui.button(
        emoji="⬆", label="Move Up", style=discord.ButtonStyle.primary, row=1
    )
    async def move_up(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        elif self.current_pos != 0:
            await self.wiz.insert_question(
                self.current_pos - 1,
                self.wiz.questions[self.current_pos]["text"],
                self.wiz.questions[self.current_pos]["type"],
                self.wiz.questions[self.current_pos]["required"],
            )
            await self.wiz.delete_question(self.current_pos + 1)
            await self.wiz.update_embed()
            self.current_pos -= 1
            self.selector.update(self.wiz.questions, self.current_pos)
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                embed=await ef.fail("This Question Is Already On The Top"),
                ephemeral=True,
            )

    @discord.ui.button(
        emoji="🔃", label="Edit", style=discord.ButtonStyle.primary, row=1
    )
    async def edit_question(
        self, button: discord.Button, interaction: discord.Interaction
    ):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        modal = AddQuestion(self.wiz, self.current_pos)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.selector.update(self.wiz.questions, default=self.current_pos)
        await self.wiz.update_embed()
        await self.message.edit(view=self)

    @discord.ui.button(
        emoji="⬇", label="Move Down", style=discord.ButtonStyle.primary, row=1
    )
    async def move_down(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        elif self.current_pos != len(self.wiz.questions) - 1:
            await self.wiz.insert_question(
                self.current_pos + 2,
                self.wiz.questions[self.current_pos]["text"],
                self.wiz.questions[self.current_pos]["type"],
                self.wiz.questions[self.current_pos]["required"],
            )
            await self.wiz.delete_question(self.current_pos)
            await self.wiz.update_embed()
            self.current_pos += 1
            self.selector.update(self.wiz.questions, self.current_pos)
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                embed=await ef.fail("This Question Is Already On The Bottom"),
                ephemeral=True,
            )

    @discord.ui.button(
        label="Delete Question", style=discord.ButtonStyle.red, emoji="➖", row=1
    )
    async def delete(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None or len(self.wiz.questions) == 0:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        await self.wiz.delete_question(self.current_pos)
        self.current_pos = 0
        self.selector.update(self.wiz.questions, int(self.selector.options[0].value))
        await self.wiz.update_embed()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.wiz.user_id:
            return True

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "You Did Not Start This Wizard. Use `/create` To Get Started",
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        await self.message.delete()


class AddQuestion(discord.ui.Modal):
    def __init__(self, wizard: Wizard, position: int | None = None, *args, **kwargs):
        self.wiz = wizard
        self.pos = position
        super().__init__(title="Add Question", *args, **kwargs)

        self.add_item(
            discord.ui.InputText(
                label="Question Text",
                required=True,
                max_length=MAX_QUESTION_LENGTH,
                value=self.wiz.questions[self.pos]["text"]
                if self.pos is not None
                else None,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Required",
                required=True,
                max_length=1,
                placeholder='"t" (true) or "f" (false)',
                value=("t" if self.wiz.questions[self.pos]["required"] else "f")
                if self.pos is not None
                else None,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        if self.children[1].value.lower() == "t":
            req = True
        elif self.children[1].value.lower() == "f":
            req = False
        else:
            return await interaction.response.send_message(
                embed=await ef.fail(
                    'Required Needs To Be Either "t" (True) Or "f" (False)'
                ),
                ephemeral=True,
            )
        if self.pos is not None:
            await self.wiz.delete_question(self.pos)
        await self.wiz.insert_question(
            self.pos if self.pos is not None else len(self.wiz.questions),
            self.children[0].value,
            0,
            req,
        )
        await interaction.response.send_message(
            f"Question {'Added' if self.pos is None else 'Edited'}", ephemeral=True
        )


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
                    required=question["required"],
                )
            )

    async def callback(self, interaction: discord.Interaction):
        responses = self.children
        responses = [x for x in self.children if x.value]
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
        await interaction.response.send_message(
            "You Completed The Survey!", ephemeral=True
        )


class SurveyButton(discord.ui.View):
    def __init__(
        self, survey, custom_id: str, end_time: datetime.datetime = None, **kwargs
    ):
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
        start_button = discord.ui.Button(
            label="Take Survey", style=discord.ButtonStyle.primary, custom_id=custom_id
        )
        start_button.callback = self.start_survey
        self.add_item(start_button)

    def is_persistent(self) -> bool:
        return all(item.is_persistent() for item in self.children)

    async def start_survey(self, interaction):
        if self.message is None:
            self._message = interaction.message
        if self.end_time and self.end_time < datetime.datetime.now():
            await interaction.response.send_message(
                embed=await ef.fail(
                    "This Survey Is Now Closed As The End Date Has Been Reached"
                ),
                ephemeral=True,
            )
            return await self._close_survey()

        sql = """SELECT DISTINCT max(response_num) FROM responses 
        WHERE user_id=$2 and active_survey_id = $1;"""
        times_taken = await db.fetch(sql, int(self.custom_id), interaction.user.id)

        if self.entries_per is not None and times_taken[0][0] is not None:
            if times_taken[0][0] >= self.entries_per:
                return await interaction.response.send_message(
                    embed=await ef.fail(
                        "You Have Taken This Survey The Maximum Number Of Times Allowed"
                    ),
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

        sql = "SELECT text, type, position, required, id FROM questions WHERE survey_id=$1;"
        await interaction.response.send_modal(
            SurveyModel(
                int(self.custom_id), self.name, await db.fetch(sql, self.template_id)
            )
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
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str, description="The Name For This Survey", max_length=64, required=True
        ),
    ):
        # await ctx.defer()
        # Ensure That No Other Survey In The Guild Has The Same Name
        sql = """SELECT name FROM guild_surveys WHERE name=$1 AND guild_id=$2"""
        result = await db.fetch(sql, name, ctx.guild.id)
        if result:
            return await ctx.respond(
                embed=await ef.fail("There Is Already A Survey With That Name"),
                ephemeral=True,
            )

        em = discord.Embed(
            title="Survey Creation Wizard",
            description="""Edit the settings for your survey. Any option that is not filled will
                           default to the displayed value or none.""",
            fields=[
                discord.EmbedField(name="Survey Name", value=name),
                discord.EmbedField(name="Questions", value="No Questions", inline=True),
                discord.EmbedField(name="Required", value="", inline=True),
                discord.EmbedField(name="Type", value="", inline=True),
                discord.EmbedField(
                    name="User Settings",
                    value="**[WIP]** Anonymous: No\nNumber Of Entries Per Person: 1\n**[WIP]** Edit "
                    "Responses: No",
                ),
                discord.EmbedField(
                    name="Survey Settings",
                    value="Time Limit: None\nTotal Number Of Entries: None",
                ),
            ],
        )
        view = Wizard(em, ctx.author.id, name)
        await ctx.respond(embed=view.embed, view=view)
        if await view.wait():
            await ctx.send_followup(
                "Survey Creation Timed Out. Remember Only 15 Minutes Is Given"
            )

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
            return [
                name for name in results if name.lower().startswith(ctx.value.lower())
            ]

    @tasks.loop(minutes=3)
    async def _clear_cache(self):
        self.survey_name_cache = {}

    @slash_command(description="Opens The Survey For Submissions")
    @discord.default_permissions(manage_guild=True)
    async def attach(
        self,
        ctx,
        name: Option(
            str,
            name="survey",
            description="The Survey To Attach",
            autocomplete=get_surveys,
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
        if name == "No Surveys Found. Use /create To Make One":
            return ctx.respond(
                embed=await ef.fail("I Told You You Needed To Use /create >:("),
                ephemeral=True,
            )

        sql = """SELECT id AS template_id, guild_id, anonymous, editable, entries_per, total_entries, time_limit, name 
        FROM guild_surveys WHERE guild_id = $1 AND name = $2;"""
        survey = await db.fetch(sql, ctx.guild.id, name)

        if not survey:
            return await ctx.respond(
                embed=await ef.fail(
                    "There Is No Survey With This Name. Try Selecting One Of The Provided Options."
                ),
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
            content="",
            embed=e,
            view=SurveyButton(survey[0], str(button_id[0]["id"]), end_time=end),
        )

    @slash_command(
        description="Close A Survey Before The Time Limit Or Max Amount Of Entries Has Been Reached"
    )
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
        return await ctx.respond(
            embed=await ef.success("The Survey Was Closed!"), ephemeral=True
        )

    @slash_command(description="View The Results And Responses Of A Survey")
    @discord.default_permissions(manage_guild=True)
    async def results(
        self,
        ctx,
        survey: Option(
            str,
            description="The Survey To See The Results Of",
            autocomplete=get_surveys,
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
        if survey == "No Surveys Found. Use /create To Make One":
            return await ctx.respond(
                embed=await ef.fail("I Told You You Needed To Use /create >:("),
                ephemeral=True,
            )

        sql = """SELECT id FROM guild_surveys WHERE guild_id = $1 AND name = $2;"""
        survey_row = await db.fetch(sql, ctx.guild.id, survey)

        if not survey_row:
            return await ctx.respond(
                embed=await ef.fail(
                    "There Is No Survey With This Name. Try Selecting One Of The Provided Options."
                ),
                ephemeral=True,
            )

        # Get Questions
        sql = """SELECT id, type, text, position FROM questions WHERE survey_id=$1"""
        questions = await db.fetch(sql, survey_row[0]["id"])

        questions = {q["id"]: (q["position"], q["type"], q["text"]) for q in questions}
        survey_description = discord.Embed(
            title=f"Results For {survey}",
            description="\n".join([f"{q[0]}. {q[2]}" for q in questions.values()]),
        )

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
            if current_length + len(response["response"]) > 1024 or len(e.fields) >= 8:
                embeds.append([survey_description, e])
                e = discord.Embed()
                current_length = 0
            e.add_field(
                name=f"Question {questions[response['question_id']][0] + 1}",
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
            self.bot.add_view(view)


def setup(bot):
    bot.add_cog(Survey(bot))
