from typing import TYPE_CHECKING

import discord
from discord import slash_command, Option

from forms.survey.template import SurveyTemplate, title_autocomplete, get_templates
from questions.multiple_choice import MultipleChoice
from questions.survey_question import SurveyQuestion, QuestionType
from questions.text_question import TextQuestion
from utils import embed_factory as ef
from utils.timers import Timer
from utils.database import database as db


def toggle_button(state: bool):
    state = not state
    options = {
        True: [discord.ButtonStyle.green, "✅"],
        False: [discord.ButtonStyle.grey, "❌"],
    }
    return state, options[state][0], options[state][1]


class Wizard(discord.ui.View):
    def __init__(self, template: SurveyTemplate, user_id: int):
        super().__init__(timeout=600)
        self.template = template
        self.user_id = user_id

        self._edit_question_interaction: discord.Interaction | None = None

    async def _create_embed(self) -> discord.Embed:
        e = discord.Embed(
            title="Survey Creation Wizard",
            description="Edit the settings for your survey. Any option that is not filled will default to the "
            "displayed value or none.",
            fields=[
                discord.EmbedField(name="Survey Name", value=self.template.title),
                discord.EmbedField(
                    name="User Settings",
                    value=f"""
                    **[WIP]** Anonymous: {self.template.anonymous.name.capitalize()}
                    Number Of Entries Per Person: {self.template.entries_per_user}
                    **[WIP]** Edit Responses: {self.template.editable_responses}
                    """,
                ),
                discord.EmbedField(
                    name="Survey Settings",
                    value=f"""
                    Default Time Limit: {self.template.duration}
                    Total Number Of Entries: {self.template.max_entries}
                    """,
                ),
            ],
        )
        return e

    async def update_message(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(view=self, embed=await self._create_embed())

    @discord.ui.button(label="Edit Questions", style=discord.ButtonStyle.primary)
    async def edit_questions(self, button, interaction):
        editor = EditQuestions(self)
        await editor.update_button_state()
        try:
            if self._edit_question_interaction is not None:
                await self._edit_question_interaction.delete_original_response()
        except discord.errors.NotFound:
            pass

        self._edit_question_interaction = await interaction.response.send_message(
            view=editor,
            embed=await editor.create_question_embed(),
        )

    @discord.ui.button(
        label="[WIP] Anonymous",
        style=discord.ButtonStyle.green,
        emoji="✅",
        disabled=True,
    )
    async def anon_toggle(self, button, interaction):
        self.template.anonymous, button.style, button.emoji = toggle_button(bool(self.template.anonymous))
        await self.update_message(interaction)

    @discord.ui.button(
        label="[WIP] Edit Responses",
        style=discord.ButtonStyle.grey,
        emoji="❌",
        disabled=True,
    )
    async def edit_toggle(self, button, interaction):
        self.template.editable_responses, button.style, button.emoji = toggle_button(self.template.editable_responses)
        await self.update_message(interaction)

    @discord.ui.button(label="Set Other Settings", style=discord.ButtonStyle.primary)
    async def set_misc(self, button, interaction):
        return await interaction.response.send_modal(SetSettings(self))

    @discord.ui.button(label="Save And Exit", style=discord.ButtonStyle.green, row=4)
    async def save(self, button, interaction):
        if not self.template.questions:
            return await interaction.response.send_message(
                embed=await ef.fail("Please Set At Least One Question"), ephemeral=True
            )

        await interaction.response.defer()
        await self.template.save()

        self.disable_all_items()
        self.stop()
        await interaction.edit_original_response(
            view=self, embeds=[await ef.general("The Survey Was Saved"), await self._create_embed()]
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=await ef.fail("You Did Not Start This Wizard. Use `/create` To Get Started"),
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        message = "Remember That Only 10 Minutes Is Given Between Interacting With The Wizard"
        if len(self.template.questions) > 0:
            await self.template.save()
            message += "\nSome Of The Information Was Saved. To Continue Editing Use </edit:1196819300216999987>"
        await self.message.edit(
            view=None,
            embeds=[
                await self._create_embed(),
                await ef.general("Creation Timed Out", message),
            ],
        )


class SetSettings(discord.ui.Modal):
    def __init__(self, wiz: Wizard, *args, **kwargs) -> None:
        self.wiz = wiz
        self.template = wiz.template
        super().__init__(title="Set Other Settings", *args, **kwargs)

        self.add_item(
            discord.ui.InputText(
                label="Number Of Entries Per Person",
                required=False,
                placeholder='The Default Value For "Number Of Entries Per Person" Is 1',
                value=str(self.template.entries_per_user or 1),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Time Limit",
                required=False,
                placeholder='The Default Value For "Time Limit" Is No Time Limit',
                value=str(self.template.duration) if self.template.duration else "None",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Total Number Of Entries",
                required=False,
                placeholder='The Default Value For "Total Number Of Entries" Is No Limit',
                value=str(self.template.max_entries),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Validate Inputs
        errors = []
        # Num Entries
        if self.children[0].value.lower() == "none" or self.children[0].value == "":
            self.template.entries_per_user = 1
        else:
            try:
                v = int(self.children[0].value)
                if v < 1 or v > 20:
                    errors.append("Number Of Entries Per Person Must Be 1 Through 20")
                else:
                    self.template.entries_per_user = v
            except ValueError:
                errors.append(
                    "Number Of Entries Per Person Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )

        # Time Limit
        if self.children[1].value.lower() == "none" or self.children[1].value == "":
            self.template.duration = None
        elif Timer.str_time(self.children[1].value).total_seconds() == 0:
            errors.append(
                """You Entered A Value For `Duration Override` But It Was Not Valid. 
                You Should Write The Time In This Format: `2 hours and 15 minutes`.
                Abbreviations Like `min` Or `m` For Minutes Are Also Allowed."""
            )
        else:
            self.template.duration = Timer.str_time(self.children[1].value)

        # Total Num Entries
        if self.children[2].value.lower() == "none" or self.children[2].value == "":
            self.template.max_entries = None
        else:
            try:
                v = int(self.children[2].value)
                if v < 1 or v > 20000:
                    errors.append("Total Number Of Entries Must Be 1 Through 20,000")
                else:
                    if v == 0:
                        self.template.max_entries = None
                    else:
                        self.template.max_entries = v
            except ValueError:
                errors.append(
                    "Total Number Of Entries Must Be A Whole Number (No Letters Or Symbols Including `.` And `,`)"
                )
        await self.wiz.update_message(interaction)
        if errors:
            em = discord.Embed(
                title="Some Settings Failed",
                description="Below Are The Errors Of The Settings That Were Not Inputted Correctly. If "
                "There Is Not An Error The Setting Was Successfully Set.",
                color=0xD33033,
            )
            em.add_field(name="Errors", value="\n".join(errors))
            await interaction.followup.send(embed=em)


class EditQuestions(discord.ui.View):
    def __init__(self, wizard: Wizard):
        super().__init__()
        self.wiz = wizard
        self.question_selector = QuestionSelector(self.wiz.template.questions)
        self.add_item(self.question_selector)

        if len(self.wiz.template.questions) > 0:
            self.current_pos = 0
            self.question_selector.update(self.wiz.template.questions, self.current_pos)
        else:
            self.current_pos: int = -1

    async def create_question_embed(self) -> discord.Embed:
        if self.current_pos == -1:
            return await ef.general(
                title="Add A Question Below",
                message="You Have Not Created A Question Yet. Please Use The Dropdown Below To Create One",
            )
        else:
            return await self.wiz.template.questions[self.current_pos].display()

    async def update_button_state(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = False
        if self.current_pos == -1:
            self.move_up.disabled = True
            self.move_down.disabled = True
            self.edit_question.disabled = True
            self.delete.disabled = True
        elif self.current_pos == 0:
            self.move_up.disabled = True
        if self.current_pos == len(self.wiz.template.questions) - 1:
            self.move_down.disabled = True

        if len(self.wiz.template.questions) <= 1:
            self.question_selector.disabled = True

    async def move(self, direction: int):
        """
        Moves The Question In The Proper Direction
        :arg direction -1 for up 1 for down
        """
        qs = self.wiz.template.questions
        temp = qs[self.current_pos]
        qs[self.current_pos] = qs[self.current_pos + direction]
        qs[self.current_pos + direction] = temp

        self.current_pos += direction
        self.question_selector.update(qs, self.current_pos)
        await self.update_button_state()

    @discord.ui.button(emoji="⬆", label="Move Up", style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def move_up(self, button: discord.Button, interaction: discord.Interaction):
        await self.move(-1)
        await interaction.response.edit_message(view=self, embed=await self.create_question_embed())

    @discord.ui.button(emoji="🔃", label="Edit", style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def edit_question(self, button: discord.Button, interaction: discord.Interaction):
        interaction = await self.wiz.template.questions[self.current_pos].set_up(interaction)
        self.question_selector.update(self.wiz.template.questions, default=self.current_pos)
        await interaction.response.edit_message(view=self, embed=await self.create_question_embed())

    @discord.ui.button(emoji="⬇", label="Move Down", style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def move_down(self, button: discord.Button, interaction: discord.Interaction):
        await self.move(1)
        await interaction.response.edit_message(view=self, embed=await self.create_question_embed())

    @discord.ui.button(label="Delete Question", style=discord.ButtonStyle.red, emoji="➖", row=1, disabled=True)
    async def delete(self, button: discord.Button, interaction: discord.Interaction):
        q = self.wiz.template.questions.pop(self.current_pos)
        await q.delete()
        if len(self.wiz.template.questions) == 0:
            self.current_pos = -1
        else:
            self.current_pos = 0
        self.question_selector.update(self.wiz.template.questions, self.current_pos)
        await self.update_button_state()
        await interaction.response.edit_message(view=self, embed=await self.create_question_embed())

    options = [
        discord.SelectOption(
            label="Text Response",
            description="Allows The User To Type Whatever They Want",
            value=str(QuestionType.TEXT.value),
            emoji="📜",
        ),
        discord.SelectOption(
            label="Multiple Choice",
            description="The User Must Choose From A List Of Options",
            value=str(QuestionType.MULTIPLE_CHOICE.value),
            emoji="🇦",
        ),
    ]

    @discord.ui.select(placeholder="Add New Question", options=options, row=4)
    async def add_question(self, select: discord.ui.Select, interaction: discord.Interaction):
        if len(self.wiz.template.questions) >= 25:
            return await interaction.response.send_message(
                embed=await ef.fail("You Cannot Have More Then 25 Questions."),
                ephemeral=True,
            )
        match int(select.values[0]):
            case QuestionType.TEXT.value:
                question = TextQuestion("New Question", self.wiz.template._id)
            case QuestionType.MULTIPLE_CHOICE.value:
                question = MultipleChoice("New Question", self.wiz.template._id)
            case _:
                raise ValueError(f"Invalid Question Type {select.values[0]}")
        await self.wiz.template.add_question(question, self.current_pos + 1)
        interaction = await question.set_up(interaction)

        self.current_pos = self.current_pos + 1
        self.question_selector.update(self.wiz.template.questions, default=self.current_pos)
        await self.update_button_state()

        await interaction.response.edit_message(view=self, embed=await self.create_question_embed())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.wiz.user_id:
            return True

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "You Did Not Start This Wizard. Use `/create` To Get Started",
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        if self.message is not None:
            await self.message.delete()


class QuestionSelector(discord.ui.Select):
    def __init__(self, questions: list[SurveyQuestion]):
        super().__init__(placeholder="Select A Question To Edit", row=0, disabled=True)
        self.update(questions)

    if TYPE_CHECKING:

        @property
        def view(self) -> EditQuestions: ...

    def update(self, questions: list[SurveyQuestion], default: int = -1):
        self.options = [
            discord.SelectOption(label=f"{n + 1}. {x.title}", value=str(n), default=(n == default))
            for n, x in enumerate(questions)
        ]
        if len(self.options) == 0:
            self.options = [discord.SelectOption(label="No Questions Have Been Created Yet", value="-1")]

    async def callback(self, interaction: discord.Interaction):
        if int(self.values[0]) != -1:
            self.view.current_pos = int(self.values[0])
            self.update(self.view.wiz.template.questions, self.view.current_pos)
            await self.view.update_button_state()
            await interaction.response.edit_message(view=self.view, embed=await self.view.create_question_embed())


class DeleteSurveyConf(discord.ui.View):
    def __init__(self, template: SurveyTemplate):
        self.template = template
        super().__init__()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.green)
    async def cancel(self, button, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=await ef.success(f"The **{self.template.title}** Survey Was **NOT** Deleted"), view=None
        )
        self.stop()

    @discord.ui.button(label="DELETE", emoji="⚠", style=discord.ButtonStyle.red)
    async def delete_survey_button(self, button, interaction: discord.Interaction):
        await self.template.delete()
        await interaction.response.edit_message(
            embed=await ef.success(f"The **{self.template.title}** Survey Was Deleted"), view=None
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
        if await SurveyTemplate.check_exists(name, ctx.guild.id):
            return await ctx.respond(
                embed=await ef.fail("There Is Already A Survey With That Name"),
                ephemeral=True,
            )

        view = Wizard(SurveyTemplate(name, ctx.guild.id), user_id=ctx.author.id)
        await ctx.respond(embed=await view._create_embed(), view=view)

    @slash_command(name="delete", description="Delete A Survey")
    @discord.default_permissions(manage_guild=True)
    async def delete_survey(
        self,
        ctx: discord.ApplicationContext,
        name: Option(
            str,
            name="survey",
            description="The Survey To Delete",
            autocomplete=title_autocomplete,
        ),
    ):
        for template in await get_templates(ctx.guild_id):
            if name == str(template._id) or name == template.title:
                name = template.title
                break
        else:
            return await ctx.respond(embed=await ef.fail(f"No Survey Named `{name}` Found"), ephemeral=True)
        sql1 = "SELECT COUNT(*) FROM surveys.questions WHERE survey_id = $1;"
        sql2 = """
        SELECT COUNT(*) FROM surveys.question_response WHERE question IN 
        (SELECT id FROM surveys.questions WHERE survey_id=$1);
        """
        message = f"""This Survey Has: 
            `{await db.fetchval(sql1, template._id)}` Questions
            `{await db.fetchval(sql2, template._id)}` Responses"""
        await ctx.respond(
            embed=await ef.general(f"Are You Sure You Want To Delete {name}?", message=message),
            view=DeleteSurveyConf(template),
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
            autocomplete=title_autocomplete,
        ),
    ):
        templates = await get_templates(ctx.guild_id)
        for template in templates:
            if name == str(template._id) or name == template.title:
                break
        else:
            return await ctx.respond(embed=await ef.fail(f"No Survey Named `{name}` Found"), ephemeral=True)
        await template.fill_questions()
        wiz = Wizard(template, ctx.author.id)
        await ctx.respond(embed=await wiz._create_embed(), view=wiz)


def setup(bot):
    bot.add_cog(CreationCog(bot))
