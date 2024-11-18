import discord
from discord import slash_command, Option
from datetime import timedelta
from utils.timers import Timer
from utils.database import database as db
from utils import embed_factory as ef
from utils.db_classes import BaseQuestion, TextQuestion, Survey, QuestionType, MCQuestion
from cogs.survey.old_survey import toggle_button, MAX_QUESTION_LENGTH, survey_name_cache, survey_name_autocomplete, get_survey


class Wizard(discord.ui.View):
    def __init__(self, user: int, name: str):
        # Question Text, Type, Required, Position
        self.questions: list[BaseQuestion] = []
        self.anonymous: bool = True
        self.edit_responses: bool = False
        self.num_entries: int = 1
        self.time_limit: timedelta | None = None
        self.tnum_entries: int | None = None
        self.name: str = name
        self.user_id: int = user
        self.embed: discord.Embed = discord.Embed(
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
                    value="**[WIP]** Anonymous: No\nNumber Of Entries Per Person: 1\n**[WIP]** Edit " "Responses: No",
                ),
                discord.EmbedField(
                    name="Survey Settings",
                    value="Time Limit: None\nTotal Number Of Entries: None",
                ),
            ],
        )
        super().__init__(timeout=900)

    async def update_embed(self, show: bool = True):
        em = discord.Embed(
            title="Survey Creation Wizard",
            description="Edit the settings for your survey. Any option that is not filled will default to the "
                        "displayed value or none.",
            fields=[
                discord.EmbedField(name="Survey Name", value=self.name),
                discord.EmbedField(
                    name="Questions",
                    value="\n".join([f"{n + 1} - " + x.text for n, x in enumerate(self.questions)])
                    or "No Questions",
                    inline=True,
                ),
                discord.EmbedField(
                    name="Required",
                    value="\n".join([str(x.required) for x in self.questions]),
                    inline=True,
                ),
                discord.EmbedField(
                    name="Type",
                    value="\n".join([QuestionType.to_text[x.q_type] for x in self.questions]),
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
        if show:
            await self.message.edit(embed=em, view=self)

    async def insert_question(self, position: int, question: BaseQuestion):
        self.questions.insert(
            position,
            question
        )

    async def delete_question(self, position: int):
        self.questions.pop(position)

    @discord.ui.button(label="Edit Questions", style=discord.ButtonStyle.primary)
    async def edit_questions(self, button, interaction):
        await interaction.response.send_message(
            view=EditQuestions(self),
            embed=await ef.general(
                title="Add A Question Below",
                message="You Have Not Created A Question Yet. Please Use The Dropdown Below To Create One"
            )
        )

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
        self.edit_responses, button.style, button.emoji = toggle_button(self.edit_responses)
        await self.update_embed()
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label="Set Other Settings", style=discord.ButtonStyle.primary)
    async def set_misc(self, button, interaction):
        return await interaction.response.send_modal(SetSettings(self))

    @discord.ui.button(label="Save And Exit", style=discord.ButtonStyle.green, row=4)
    async def save(self, button, interaction):
        if not self.questions:
            return await interaction.response.send_message("Please Set At Least One Question", ephemeral=True)
        await interaction.response.defer()

        # Update The Survey If It Already Exists
        if hasattr(self, "db_id"):
            sql = """UPDATE surveys.guild_surveys SET anonymous=$1, editable=$2, entries_per=$3, total_entries=$4, time_limit=$5
            WHERE id=$6;"""
            await db.execute(
                sql,
                self.anonymous,
                self.edit_responses,
                self.num_entries,
                self.tnum_entries,
                self.time_limit,
                self.db_id,
            )
            s_id = self.db_id
        else:
            sql = """INSERT INTO surveys.guild_surveys (guild_id, anonymous, editable, entries_per, total_entries, time_limit, name)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING currval('surveys.guild_surveys_id_seq');"""
            s_id = await db.fetch(
                sql,
                interaction.guild.id,
                self.anonymous,
                self.edit_responses,
                self.num_entries,
                self.tnum_entries,
                self.time_limit,
                self.name,
            )
            s_id = s_id[0]["currval"]

        async def _insert_questions():
            sql = """INSERT INTO surveys.questions (survey_id, text, type, position, required) SELECT $5,
                                unnest($1::varchar[]), unnest($2::smallint[]), unnest($3::integer[]), unnest($4::bool[]);"""
            await db.execute(
                sql,
                [x.text for x in self.questions],
                [x.q_type for x in self.questions],
                [x.pos for x in self.questions],
                [x.required for x in self.questions],
                s_id,
            )

        # Update Questions If They Already Exist
        if hasattr(self, "has_responses"):
            # If There Are No Responses Just Delete The Questions And Re-Add Them
            if not self.has_responses:
                sql = """DELETE FROM surveys.questions WHERE survey_id=$1;"""
                await db.execute(sql, s_id)
                await _insert_questions()
                # sql = """UPDATE surveys.questions SET text=unnest($1::varchar[]), type=unnest($2::smallint[]),
                # position=unnest($3::integer[]), required=unnest($4::bool[]) WHERE id=$5;"""
                # sql = """UPDATE surveys.questions SET text=c.text, type=c.type, position=c.position, required=c.required
                # FROM (SELECT * FROM UNNEST(
                # $5::integer[], $1::varchar[], $2::smallint[], $3::integer[], $4::bool[])
                # )
                # AS c(id, text, type, position, required) WHERE c.id=surveys.questions.id"""
                # await db.execute(
                #     sql,
                #     [x.text for x in self.questions],
                #     [x.q_type for x in self.questions],
                #     [x.pos for x in self.questions],
                #     [x.required for x in self.questions],
                #     [x.q_id for x in self.questions],
                # )

        else:
            await _insert_questions()
        self.disable_all_items()
        self.stop()
        await interaction.edit_original_response(content="The Survey Was Saved", view=self, embed=self.embed)

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

    @classmethod
    async def edit(cls, survey: Survey, user_id: int):
        filled_wiz = cls(user_id, survey.name)
        filled_wiz.db_id = survey.id

        # Edit Wizard To Compensate For Already Having Responses
        sql = """SELECT active_survey_id FROM surveys.responses WHERE active_survey_id IN 
        (SELECT id FROM surveys.active_guild_surveys WHERE template_id=$1) LIMIT 1;"""
        filled_wiz.has_responses = bool(len(await db.fetch(sql, survey.id)))
        if filled_wiz.has_responses:
            # TODO: Disable Edit Questions Button BELOW RETURNS NONE
            edit_q_button = discord.utils.get(filled_wiz.children, callback__func=True, func=cls.edit_questions)
            print(f"edit_q_button: {edit_q_button}")
            filled_wiz.remove_item(edit_q_button)

        filled_wiz.anonymous = survey.anonymous
        filled_wiz.edit_responses = survey.editable
        filled_wiz.num_entries = survey.entries_per
        filled_wiz.tnum_entries = survey.total_entries
        filled_wiz.time_limit = survey.time_limit
        filled_wiz.questions = await survey.get_questions()

        await filled_wiz.update_embed(show=False)
        return filled_wiz


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
    def __init__(self, questions: list[BaseQuestion]):
        super().__init__(placeholder="Select A Question To Edit", row=0)
        self.update(questions)

    def update(self, questions: list[BaseQuestion], default=None):
        self.options = [
            discord.SelectOption(label=f"{n + 1}. {x.text}", value=str(n))
            if n != default
            else discord.SelectOption(label=f"{n + 1}. {x.text}", value=str(n), default=True)
            for n, x in enumerate(questions)
        ]
        if len(self.options) == 0:
            self.options = [discord.SelectOption(label="No Questions Have Been Created Yet", value="-1")]

    async def callback(self, interaction: discord.Interaction):
        if int(self.values[0]) != -1:
            self.view.current_pos = int(self.values[0])
            self.update(self.view.wiz.questions, self.view.current_pos)
            await interaction.response.edit_message(view=self.view, embed=await self.view._create_question_message())

class EditQuestions(discord.ui.View):
    def __init__(self, wizard: Wizard):
        super().__init__()
        self.wiz = wizard
        self.current_pos = None

        self.question_selector = QuestionSelector(self.wiz.questions)
        self.add_item(self.question_selector)

    async def _create_question_message(self) -> discord.Embed:
        if self.current_pos is None:
            return await ef.general(
                title="Add A Question Below",
                message="You Have Not Created A Question Yet. Please Use The Dropdown Below To Create One"
            )
        else:
            current_q = self.wiz.questions[self.current_pos]
            info = str(current_q).split("\n", 1)
            return await ef.general(
                title=current_q.text,
                message=info[1]
            )

    @discord.ui.button(emoji="⬆", label="Move Up", style=discord.ButtonStyle.primary, row=1)
    async def move_up(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        elif self.current_pos != 0:
            await self.wiz.insert_question(
                self.current_pos - 1,
                self.wiz.questions[self.current_pos],
            )
            await self.wiz.delete_question(self.current_pos + 1)
            await self.wiz.update_embed()
            self.current_pos -= 1
            self.question_selector.update(self.wiz.questions, self.current_pos)
            await interaction.response.edit_message(view=self, embed=await self._create_question_message())
        else:
            await interaction.response.send_message(
                embed=await ef.fail("This Question Is Already On The Top"),
                ephemeral=True,
            )

    @discord.ui.button(emoji="🔃", label="Edit", style=discord.ButtonStyle.primary, row=1)
    async def edit_question(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        modal = AddQuestion(self.wiz, self.current_pos)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.question_selector.update(self.wiz.questions, default=self.current_pos)
        await self.wiz.update_embed()
        await self.message.edit(view=self, embed=await self._create_question_message())

    @discord.ui.button(emoji="⬇", label="Move Down", style=discord.ButtonStyle.primary, row=1)
    async def move_down(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        elif self.current_pos != len(self.wiz.questions) - 1:
            await self.wiz.insert_question(
                self.current_pos + 2,
                self.wiz.questions[self.current_pos],
            )
            await self.wiz.delete_question(self.current_pos)
            await self.wiz.update_embed()
            self.current_pos += 1
            self.question_selector.update(self.wiz.questions, self.current_pos)
            await interaction.response.edit_message(view=self, embed=await self._create_question_message())
        else:
            await interaction.response.send_message(
                embed=await ef.fail("This Question Is Already On The Bottom"),
                ephemeral=True,
            )

    @discord.ui.button(label="Delete Question", style=discord.ButtonStyle.red, emoji="➖", row=1)
    async def delete(self, button: discord.Button, interaction: discord.Interaction):
        if self.current_pos is None or len(self.wiz.questions) == 0:
            return await interaction.response.send_message(
                embed=await ef.fail("You Do Not Have A Question Selected"),
                ephemeral=True,
            )
        await self.wiz.delete_question(self.current_pos)
        self.current_pos = 0
        self.question_selector.update(self.wiz.questions, int(self.question_selector.options[0].value))
        await self.wiz.update_embed()
        await interaction.response.edit_message(view=self, embed=await self._create_question_message())

    options = [
            discord.SelectOption(label="Text Response", description="Allows The User To Type Whatever They Want",
                                 value=str(QuestionType.text)),
            discord.SelectOption(label="Multiple Choice", description="The User Must Choose From A List Of Options",
                                 value=str(QuestionType.multiple_choice))
        ]
    @discord.ui.select(placeholder="Add New Question", options=options, row=4)
    async def add_question(self, select: discord.ui.Select, interaction: discord.Interaction):
        print(self.wiz.questions)
        if len(self.wiz.questions) >= 5:
            return await interaction.response.send_message(
                embed=await ef.fail(
                    "You Cannot Have More Then 5 Questions. I Know It Is Dumb But There Is Not A Good Way To Get "
                    "Around It Currently. A Work Around Will Be Added In The Future. Blame Discord"
                ),
                ephemeral=True,
            )
        modal = AddQuestion(self.wiz, None, int(select.values[0]))
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.current_pos = len(self.wiz.questions) - 1
        self.question_selector.update(self.wiz.questions, default=self.current_pos)
        await self.wiz.update_embed()
        # TODO: waiting for the modal breaks as MC choices are not complete yet
        await self.message.edit(view=self, embed=await self._create_question_message())


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

class MCQuestionCreation(discord.ui.View):
    def __init__(self, question: MCQuestion):
        self.question = question
        super().__init__()

    @discord.ui.button(label="Add Multiple Choice Options")
    async def add_mc(self, button: discord.ui.Button, interaction: discord.Interaction):
        m = AddMCChoices(self.question)
        await interaction.response.send_modal(m)
        await m.wait()


class AddMCChoices(discord.ui.Modal):
    def __init__(self, question: MCQuestion) -> None:
        self.question = question
        fields = [
            discord.ui.InputText(label="Multiple Choice Option One", placeholder="Required", required=True),
            discord.ui.InputText(label="Multiple Choice Option Two", placeholder="Required", required=True),
            discord.ui.InputText(label="Multiple Choice Option Three", placeholder="Optional", required=False),
            discord.ui.InputText(label="Multiple Choice Option Four", placeholder="Optional", required=False),
            discord.ui.InputText(label="Multiple Choice Option Five",
                                 placeholder="Optional, currently the limit is 5 multiple choice options",
                                 required=False),
        ]
        super().__init__(*fields, title=question.text, timeout=600)

    async def callback(self, interaction: discord.Interaction):
        results = [x.value for x in self.children if x]
        self.question.options = results
        await interaction.respond("Question Added!", ephemeral=True)

class AddQuestion(discord.ui.Modal):
    def __init__(self, wizard: Wizard, position: int | None = None, qtype: int = None, *args, **kwargs):
        self.wiz = wizard
        self.pos = position
        self.qtype = qtype
        super().__init__(title="Add Question", *args, **kwargs)

        self.add_item(
            discord.ui.InputText(
                label="Question Text",
                required=True,
                max_length=MAX_QUESTION_LENGTH,
                value=self.wiz.questions[self.pos].text if self.pos is not None else None,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Required",
                required=True,
                max_length=1,
                placeholder='"t" (true) or "f" (false)',
                value=("t" if self.wiz.questions[self.pos].required else "f") if self.pos is not None else None,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        if self.children[1].value.lower() == "t":
            req = True
        elif self.children[1].value.lower() == "f":
            req = False
        else:
            return await interaction.response.send_message(
                embed=await ef.fail('Required Needs To Be Either "t" (True) Or "f" (False)'),
                ephemeral=True,
            )
        if self.pos is not None:
            await self.wiz.delete_question(self.pos)
        # TODO: Make this support multiple questions
        pos = self.pos if self.pos is not None else len(self.wiz.questions)
        if self.qtype == QuestionType.text:
            await self.wiz.insert_question(
                pos,
                TextQuestion(self.children[0].value, pos, req)
            )
            await interaction.respond(f"Question {'Added' if self.pos is None else 'Edited'}", ephemeral=True)
        elif self.qtype == QuestionType.multiple_choice:
            q = MCQuestion(self.children[0].value, pos, req)
            await interaction.respond("Your question is almost complete! Click the button to add the choices",
                                      view=MCQuestionCreation(q), ephemeral=True)
            await self.wiz.insert_question(pos, q)



class DeleteSurveyConf(discord.ui.View):
    def __init__(self, survey: Survey):
        self.survey = survey
        super().__init__()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.green)
    async def cancel(self, button, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=await ef.success(f"The **{self.survey.name}** Survey Was **NOT** Deleted"), view=None
        )
        self.stop()

    @discord.ui.button(label="DELETE", emoji="⚠", style=discord.ButtonStyle.red)
    async def delete_survey_button(self, button, interaction: discord.Interaction):
        sql = "DELETE FROM surveys.guild_surveys WHERE guild_id=$1 AND id=$2;"
        await db.execute(sql, self.survey.guild_id, self.survey.id)
        await interaction.response.edit_message(
            embed=await ef.success(f"The **{self.survey.name}** Survey Was Deleted"), view=None
        )
        self.stop()

class CreationCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(description="Opens The Form Creation Wizard")
    @discord.default_permissions(manage_guild=True)
    async def create(
            self,
            ctx: discord.ApplicationContext,
            name: discord.Option(str, description="The Name For This Survey", max_length=64, required=True),
    ):
        # await ctx.defer()
        # Ensure That No Other Survey In The Guild Has The Same Name
        sql = """SELECT name FROM surveys.guild_surveys WHERE name=$1 AND guild_id=$2"""
        result = await db.fetch(sql, name, ctx.guild.id)
        if result:
            return await ctx.respond(
                embed=await ef.fail("There Is Already A Survey With That Name"),
                ephemeral=True,
            )

        view = Wizard(ctx.author.id, name)
        await ctx.respond(embed=view.embed, view=view)
        if await view.wait():
            await ctx.send_followup("Survey Creation Timed Out. Remember Only 15 Minutes Is Given")
        else:
            try:
                survey_name_cache[ctx.guild_id].append(name)
            except KeyError:
                survey_name_cache[ctx.guild_id] = [name]

    @slash_command(name="delete", description="Delete A Survey")
    @discord.default_permissions(manage_guild=True)
    async def delete_survey(
            self,
            ctx,
            name: Option(
                str,
                name="survey",
                description="The Survey To Delete",
                autocomplete=survey_name_autocomplete,
            ),
    ):
        survey = await get_survey(name, ctx)
        if survey is None:
            return
        sql1 = "SELECT COUNT(*) FROM surveys.questions WHERE survey_id = $1;"
        sql2 = "SELECT COUNT(*) FROM surveys.responses WHERE question_id IN (SELECT id FROM surveys.questions WHERE survey_id=$1);"
        message = f"""This Survey Has: 
            `{await db.fetchval(sql1, survey.id)}` Questions
            `{await db.fetchval(sql2, survey.id)}` Responses"""
        await ctx.respond(
            embed=await ef.general(f"Are You Sure You Want To Delete {name}?", message=message),
            view=DeleteSurveyConf(survey),
            ephemeral=True,
        )

    @slash_command(name="edit", description="Edit And Existing Survey")
    @discord.default_permissions(manage_guild=True)
    async def edit_survey(
            self,
            ctx: discord.ApplicationContext,
            name: Option(
                str,
                name="survey",
                description="The Survey To Edit",
                autocomplete=survey_name_autocomplete,
            ),
    ):
        survey = await get_survey(name, ctx)
        if survey is None:
            return
        wiz = await Wizard.edit(survey, ctx.author.id)
        await ctx.respond(embed=wiz.embed, view=wiz)

def setup(bot):
    bot.add_cog(CreationCog(bot))