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
        await interaction.respond(view=v)
        await v.wait()
        return v.interaction

    async def display(self) -> discord.Embed:
        e = discord.Embed(title=self.title, description=self.description)
        e.add_field(name="Required", value=str(self.required))
        if self.min_selects == self.max_selects:
            e.add_field(name="Selections",
                        value=f"Must Select {self.min_selects} Option{"s" if self.min_selects != 1 else ""}")
        else:
            e.add_field(name="Selections",
                        value=f"Must Select Between {self.min_selects} And {self.max_selects} Options Inclusive")
        e.add_field(name="Options", value="- " + "\n- ".join([await x.display() for x in self.options]))
        return e

    async def short_display(self) -> str:
        return f"{self.title} {self.description}"

    @staticmethod
    async def view_response(response: dict, options: list[MultipleChoiceOption] = None) -> str:
        if options is None:
            raise ValueError("options must be passed to multiple choice questions")
        options = {x.id: x.text for x in options}
        result = ", ".join([options[x] for x in response["selected"]])
        return result

    async def save_response(self, conn: Connection, encrypted_user_id: str, response_num: int, active_id: int,
                            response_id: int) -> None:
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
            "options": [x.create_data() for x in self.options]
        }

    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        m = GetMultipleChoiceQuestionInfo(self)
        await interaction.response.send_modal(m)
        await m.wait()
        interaction = m.interaction
        v = AddChoices(self)
        await interaction.response.send_message(embed=await general("Options"), view=v)
        await v.wait()
        return v.interaction

    @classmethod
    async def load(cls, row: Record):
        q: cls = await super().load(row)
        q.min_selects = row["question_data"]["min_selects"]
        q.max_selects = row["question_data"]["max_selects"]
        q.options = [MultipleChoiceOption.load(x) for x in row["question_data"]["options"]]
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

        return errors


class AddChoices(discord.ui.View):
    interaction: discord.Interaction

    class EditSelect(discord.ui.Select):
        def __init__(self, options: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in options]
            if len(display_options) == 0:
                display_options.append(discord.SelectOption(label="No Options To Edit"))
            super().__init__(options=display_options,
                             placeholder="Select A Option To Edit")
            self.question_options: list[MultipleChoiceOption] = options

        async def callback(self, interaction: Interaction):
            found = None
            for i in self.question_options:
                if int(self.values[0]) == i.id:
                    found = i
                    break
            m = Options(prefill=found)
            await interaction.response.send_modal(m)
            await m.wait()
            await m.interaction.response.edit_message(view=self.view, embed=await self.view._create_embed())

    class DeleteSelect(discord.ui.Select):
        def __init__(self, options: list[MultipleChoiceOption]):
            display_options = [discord.SelectOption(label=x.text, value=str(x.id)) for x in options]
            if len(display_options) == 0:
                display_options.append(discord.SelectOption(label="No Options To Delete"))
            super().__init__(options=display_options,
                             placeholder="Select A Option To Delete")
            self.question_options: list[MultipleChoiceOption] = options

        async def callback(self, interaction: Interaction):
            for n, i in enumerate(self.question_options):
                if int(self.values[0]) == i.id:
                    self.question_options.pop(n)
                    break
            await interaction.response.edit_message(view=self.view, embed=await self.view._create_embed())

    def __init__(self, question: MultipleChoice):
        super().__init__(timeout=300)
        self.question: MultipleChoice = question

        self.existing = self.question.options

        self.add_item(AddChoices.EditSelect(self.question.options))
        self.add_item(AddChoices.DeleteSelect(self.question.options))

    async def _create_embed(self) -> discord.Embed:
        prefix = "- " if len(self.existing) > 0 else ""
        return await general(title="Options", message=prefix + "\n- ".join([await x.display() for x in self.existing]))

    @discord.ui.button(label="Add Options", style=discord.ButtonStyle.blurple)
    async def add_options(self, button: discord.Button, interaction: discord.Interaction):
        m = Options(question=self.question)
        await interaction.response.send_modal(m)
        await m.wait()
        await m.interaction.response.edit_message(view=self, embed=await self._create_embed())

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
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
                self.view.selected.pop(self.option)
            await self.view.update(interaction)

    def __init__(self, quesiton: MultipleChoice):
        super().__init__()
        self.selected: set[MultipleChoiceOption] = set()
        self.question = quesiton
        for o in quesiton.options:
            self.add_item(ResponseView.ChoiceButton(o))

        if self.question.required:
            self.submit.disabled = True
        else:
            self.submit.disabled = False

    async def update(self, interaction: discord.Interaction):
        if len(self.selected) >= self.question.max_selects:
            for button in self.children:
                if isinstance(button, ResponseView.ChoiceButton) and button.style == discord.ButtonStyle.gray:
                    button.disabled = True
        else:
            for button in self.children:
                if isinstance(button, ResponseView.ChoiceButton):
                    button.disabled = False

        if len(self.selected) == 0:
            if self.question.required:
                self.submit.disabled = True
            else:
                self.submit.disabled = False
        elif self.question.min_selects < len(self.selected):
            self.submit.disabled = True
        else:
            self.submit.disabled = False
        interaction.response.edit_message(view=self, embed=await self._create_embed())

    async def _create_embed(self) -> discord.Embed:
        e = await self.question.display()
        e.set_footer(text="Options In Green Are Selected")
        return e

    @discord.ui.button(label="Save & Continue", style=discord.ButtonStyle.green, row=5)
    async def submit(self, button: discord.Button, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()
