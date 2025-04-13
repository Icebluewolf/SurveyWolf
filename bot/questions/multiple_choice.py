import discord
from asyncpg import Connection, Record
from discord import Interaction

from questions.survey_question import SurveyQuestion, QuestionType, GetBaseInfo
from utils.database import database as db
from utils.embed_factory import general


class MultipleChoiceOption:
    id: int | None

    def __init__(self, text: str):
        self.text: str = text
        self.id = MultipleChoice.OPTION_ID_COUNTER
        MultipleChoice.OPTION_ID_COUNTER += 1

    async def display(self) -> str:
        return self.text

    async def create_data(self) -> dict:
        return {
            "text": self.text,
            "id": self.id
        }

    @classmethod
    async def load(cls, data: dict):
        new_option = cls(data["text"])
        new_option.id = data.get("id")
        return new_option


class MultipleChoice(SurveyQuestion):
    QUESTION_TYPE = QuestionType.MULTIPLE_CHOICE

    # This Only Needs To Be Unique Per Question
    OPTION_ID_COUNTER: int = 0

    def __init__(self, title: str, survey_id: int):
        super().__init__(title, survey_id)
        self.description: str = ""
        self.required = True
        self._id = None

        self.options: list[MultipleChoiceOption] = []
        self.min_selects: int = 1
        self.max_selects: int = 1

        self.selected: set[MultipleChoiceOption] = set()

    async def send_question(self, interaction: discord.Interaction) -> discord.Interaction:
        v = ResponseView(self)
        await interaction.respond(view=v, embed=await v.create_embed(), ephemeral=True)
        await v.wait()
        return v.interaction

    async def display(self, with_options: bool = True) -> discord.Embed:
        e = discord.Embed(title=self.title, description=self.description)
        e.add_field(name="Required", value=str(self.required))
        if self.min_selects == self.max_selects:
            e.add_field(name="Selections",
                        value=f"Must Select {self.min_selects} Option{"s" if self.min_selects != 1 else ""}")
        else:
            e.add_field(name="Selections",
                        value=f"Must Select Between {self.min_selects} And {self.max_selects} Options Inclusive")
        if with_options:
            e.add_field(name="Options", value="- " + "\n- ".join([await x.display() for x in self.options]), inline=False)
        return e

    async def short_display(self) -> str:
        return f"{self.title} {self.description}"

    async def view_response(self, response: dict) -> str:
        options = {x.id: x.text for x in self.options}
        result = ", ".join([options[x] for x in response["selected"]])
        return result

    async def save_response(self, conn: Connection, encrypted_user_id: str, active_id: int, response_id: int) -> None:
        if not self.selected:
            return
        sql = """INSERT INTO surveys.question_response (response, question, response_data) VALUES ($1, $2, $3);"""
        await conn.execute(sql, response_id, self._id, await self._create_response_data())

    async def delete(self) -> None:
        sql = """DELETE FROM surveys.questions WHERE id=$1;"""
        await db.execute(sql, self._id)

    async def save(self, position: int, conn: Connection = None) -> None:
        if conn is None:
            conn = db
        if self._id:
            base_sql = """
                UPDATE surveys.questions 
                SET text=$2, position=$3, survey_id=$4, required=$5, description=$6, type=$7, question_data=$8
                WHERE id=$1;
            """
            await conn.execute(
                base_sql,
                self._id,
                self.title,
                position,
                self.template,
                self.required,
                self.description,
                MultipleChoice.QUESTION_TYPE.value,
                await self._create_data(),
            )
        else:
            base_sql = """
                        INSERT INTO surveys.questions (text, position, survey_id, required, description, type, question_data) 
                        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id;
                        """
            record = await conn.fetch(
                base_sql,
                self.title,
                position,
                self.template,
                self.required,
                self.description,
                MultipleChoice.QUESTION_TYPE.value,
                await self._create_data(),
            )
            self._id = record[0]["id"]

    async def _create_response_data(self) -> dict:
        return {
            "selected": [x.id for x in self.selected]
        }

    async def _create_data(self) -> dict:
        return {
            "min_selects": self.min_selects,
            "max_selects": self.max_selects,
            "options": [await x.create_data() for x in self.options]
        }

    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        m = GetMultipleChoiceQuestionInfo(self)
        await interaction.response.send_modal(m)
        await m.wait()
        interaction = m.interaction
        v = AddChoices(self)
        await interaction.response.edit_message(embed=await general("Options"), view=v)
        if not await v.wait():
            return v.interaction

    @classmethod
    async def load(cls, row: Record):
        q: cls = await super().load(row)
        q.min_selects = row["question_data"]["min_selects"]
        q.max_selects = row["question_data"]["max_selects"]
        q.options = [await MultipleChoiceOption.load(x) for x in row["question_data"]["options"]]
        return q


class GetMultipleChoiceQuestionInfo(GetBaseInfo):
    def __init__(self, question: MultipleChoice):
        super().__init__(question, "Add A Text Question")
        self.question: MultipleChoice = question

        self.add_item(
            discord.ui.InputText(
                label="Minimum Options To Select",
                placeholder="Must Be A Number Between 1 And 20. The Default Is 1",
                required=True,
                min_length=1,
                max_length=2,
                value=str(self.question.min_selects),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Maximum Options To Select",
                placeholder="Must Be A Number Between 1 And 20. The Default Is 1",
                required=True,
                min_length=1,
                max_length=2,
                value=str(self.question.max_selects),
            )
        )

    async def process(self):
        errors = await super().process() or []
        try:
            minimum = int(self.children[2].value)
            if 1 <= minimum <= 20:
                self.question.min_selects = minimum
            else:
                errors.append("Minimum Options To Select Needs To Be Between 1 And 20")
        except ValueError:
            errors.append("Minimum Options To Select Needs To Be A Number Between 1 And 20. Do Not Use `,` Or `.`")

        try:
            maximum = int(self.children[3].value)
            if 1 <= maximum <= 20:
                self.question.max_selects = maximum
            else:
                errors.append("Maximum Options To Select Needs To Be Between 1 And 20")
        except ValueError:
            errors.append("Maximum Options To Select Needs To Be A Number Between 1 And 20. Do Not Use `,` Or `.`")

        # The Defaults Will Always Meet This Condition So Even If There Are Other Errors We Can Still Check
        if self.question.min_selects > self.question.max_selects:
            self.question.max_selects = self.question.max_selects
            errors.append("Minimum Options Cannot Be Grater Then Maximum Options.")

        return errors


class AddChoices(discord.ui.View):
    interaction: discord.Interaction

    class EditSelect(discord.ui.Select):
        def __init__(self, options: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in options]
            disabled = False
            if len(display_options) == 0:
                display_options.append(discord.SelectOption(label="No Options To Edit"))
                disabled = True
            super().__init__(options=display_options,
                             placeholder="Select A Option To Edit", disabled=disabled)
            self.question_options: list[MultipleChoiceOption] = options

        async def update(self, selected: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in selected]
            if len(display_options) == 0:
                display_options.append(discord.SelectOption(label="No Options To Edit"))
            self.options = display_options
            self.question_options: list[MultipleChoiceOption] = selected

        async def callback(self, interaction: Interaction):
            found = None
            for i in self.question_options:
                if int(self.values[0]) == i.id:
                    found = i
                    break
            m = Options(prefill=found)
            await interaction.response.send_modal(m)
            await m.wait()
            await self.view.update(m.interaction)

    class DeleteSelect(discord.ui.Select):
        def __init__(self, options: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in options]
            disabled = False
            if len(display_options) == 0:
                disabled = True
                display_options.append(discord.SelectOption(label="No Options To Delete"))
            super().__init__(options=display_options,
                             placeholder="Select A Option To Delete", disabled=disabled)
            self.question_options: list[MultipleChoiceOption] = options

        async def update(self, selected: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in selected]
            if len(display_options) == 0:
                display_options.append(discord.SelectOption(label="No Options To Delete"))
            self.options = display_options
            self.question_options: list[MultipleChoiceOption] = selected

        async def callback(self, interaction: Interaction):
            for n, i in enumerate(self.question_options):
                if int(self.values[0]) == i.id:
                    self.question_options.pop(n)
                    break
            await self.view.update(interaction)

    def __init__(self, question: MultipleChoice):
        super().__init__(timeout=300)
        self.question: MultipleChoice = question

        self.edit_select = AddChoices.EditSelect(self.question.options)
        self.delete_select = AddChoices.DeleteSelect(self.question.options)

        self.add_item(self.edit_select)
        self.add_item(self.delete_select)

    async def _create_embed(self) -> discord.Embed:
        prefix = "- " if len(self.question.options) > 0 else ""
        return await general(title="Options", message=prefix + "\n- ".join([await x.display() for x in self.question.options]))

    async def update(self, interaction: discord.Interaction):
        if len(self.question.options) == 0:
            self.edit_select.disabled = True
            self.delete_select.disabled = True
        else:
            self.edit_select.disabled = False
            self.delete_select.disabled = False
        await self.edit_select.update(self.question.options)
        await self.delete_select.update(self.question.options)

        if len(self.question.options) < self.question.min_selects:
            self.confirm.disabled = True
        else:
            self.confirm.disabled = False

        if len(self.question.options) >= 20:
            self.add_options.disabled = True
        else:
            self.add_options.disabled = False

        await interaction.response.edit_message(view=self, embed=await self._create_embed())

    @discord.ui.button(label="Add Options", style=discord.ButtonStyle.blurple)
    async def add_options(self, button: discord.Button, interaction: discord.Interaction):
        m = Options(question=self.question)
        await interaction.response.send_modal(m)
        await m.wait()
        await self.update(m.interaction)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, disabled=True)
    async def confirm(self, button: discord.Button, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()


class Options(discord.ui.Modal):
    interaction: discord.Interaction

    def __init__(self, question: MultipleChoice = None, prefill: MultipleChoiceOption = None):
        if (question is None) == (prefill is None):
            raise AttributeError("Provide Exactly One Of question Or prefill")
        super().__init__(title="Add Options")
        self.question = question
        self.prefill = prefill

        if prefill:
            size = 1
        else:
            size = min(5, 20 - len(self.question.options))
        for i in range(size):
            self.add_item(discord.ui.InputText(
                label="Option Choice",
                placeholder="Can Be A Maximum Of 80 Characters",
                min_length=0,
                max_length=80,
                required=False,
                value=None if not prefill else prefill.text
            ))

    async def callback(self, interaction: Interaction):
        self.interaction = interaction
        self.stop()

        if self.prefill:
            self.prefill.text = self.children[0].value
            return

        for response in self.children:
            if len(response.value) == 0:
                continue
            self.question.options.append(MultipleChoiceOption(response.value))


class ResponseView(discord.ui.View):
    interaction: discord.Interaction

    class ChoiceButton(discord.ui.Button):
        def __init__(self, option: MultipleChoiceOption):
            super().__init__(label=option.text, style=discord.ButtonStyle.gray)
            self.option = option

        async def callback(self, interaction: Interaction):
            if self.style == discord.ButtonStyle.gray:
                self.style = discord.ButtonStyle.blurple
                self.view.selected.add(self.option)
            elif self.style == discord.ButtonStyle.blurple:
                self.style = discord.ButtonStyle.gray
                self.view.selected.remove(self.option)
            await self.view.update(interaction)

    class ChoiceSelect(discord.ui.Select):
        def __init__(self, question: MultipleChoice):
            super().__init__(placeholder="Select Options", min_values=question.min_selects, max_values=question.max_selects)
            self.option_map = {x.id: x for x in question.options}
            for option in question.options:
                self.add_option(label=option.text, value=str(option.id), default=option in question.selected)

        async def callback(self, interaction: Interaction):
            self.view.question.selected = {self.option_map[int(x)] for x in self.values}
            self.view.interaction = interaction
            self.view.stop()

    def __init__(self, question: MultipleChoice):
        super().__init__()
        self.question = question
        self.add_item(ResponseView.ChoiceSelect(question))
        if question.required:
            self.remove_item(self.skip)

    async def create_embed(self) -> discord.Embed:
        e = await self.question.display(False)
        return e

    @discord.ui.button(label="SKIP", style=discord.ButtonStyle.gray, row=2)
    async def skip(self, button: discord.Button, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()
