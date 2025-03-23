import discord
from asyncpg import Record, Connection

from questions.input_text_response import InputTextResponse
from questions.survey_question import QuestionType, GetBaseInfo

from utils.database import database as db


class TextQuestion(InputTextResponse):
    QUESTION_TYPE = QuestionType.TEXT

    def __init__(self, title: str, survey_id: int):
        # This constructor is meant for creating new questions
        super().__init__(title, survey_id)
        self.description: str = ""
        self.required = True
        self._id = None

        self.min_length: int = 0
        self.max_length: int = 4000

        self.value: str = ""

    async def display(self) -> discord.Embed:
        e = discord.Embed(title=self.title, description=self.description)
        e.add_field(name="Required", value=str(self.required))
        e.add_field(name="Length", value=f"Between {self.min_length} And {self.max_length} Inclusive")
        return e

    async def short_display(self) -> str:
        return f"{self.title} {self.description}"

    async def _create_data(self) -> dict:
        return {
            "min_length": self.min_length,
            "max_length": self.max_length,
        }

    async def _create_response_data(self) -> dict:
        return {
            "text": self.value,
        }

    async def save(self, position: int, conn: Connection = None) -> None:
        # Setting conn to be either a Connection or my Database object is probably bad practice
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
                TextQuestion.QUESTION_TYPE.value,
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
                TextQuestion.QUESTION_TYPE.value,
                await self._create_data(),
            )
            self._id = record[0]["id"]

    async def delete(self) -> None:
        sql = """DELETE FROM surveys.questions WHERE id=$1;"""
        await db.execute(sql, self._id)

    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        m = GetTextQuestionInfo(self)
        await interaction.response.send_modal(m)
        await m.wait()
        return m.interaction

    # @classmethod
    # async def fetch(cls, id: int):
    #     sql = """
    #     SELECT text, questions.id, position, survey_id, required, description, type, min_length, max_length
    #     FROM surveys.questions INNER JOIN surveys.text_question ON questions.id = text_question.base_id
    #     WHERE questions.id=$1;"""
    #     return await TextQuestion.load(await db.fetch_one(sql, id))

    async def save_response(
        self, conn: Connection, encrypted_user_id: str, response_num: int, active_id: int, response_id: int
    ):
        sql = """INSERT INTO surveys.question_response (response, question, response_data) VALUES ($1, $2, $3);"""
        await conn.execute(sql, response_id, self._id, await self._create_response_data())

    @classmethod
    async def load(cls, row: Record):
        q = await super().load(row)
        q.min_length = row["question_data"]["min_length"]
        q.max_length = row["question_data"]["max_length"]
        return q

    async def view_response(self, response: dict) -> str:
        result = response["text"]
        return result

    def get_input_text(self) -> discord.ui.InputText:
        return discord.ui.InputText(
                    label=self.title[: min(len(self.title), 45)],
                    min_length=self.min_length,
                    max_length=self.max_length,
                    required=self.required,
                    style=discord.InputTextStyle.long,
                )

    async def handle_input_text_response(self, text: str) -> str | None:
        self.value = text
        # Text questions have no criteria other than the length which is handled by Discord
        return None


class GetTextQuestionInfo(GetBaseInfo):
    def __init__(self, question: TextQuestion):
        super().__init__(question, "Add A Text Question")
        self.question = question

        self.add_item(
            discord.ui.InputText(
                label="Minimum Length",
                placeholder="Must Be A Number Between 0 And 4000. The Default Is 0",
                required=True,
                min_length=1,
                max_length=4,
                value=str(self.question.min_length),
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Maximum Length",
                placeholder="Must Be A Number Between 1 And 4000. The Default Is 4000",
                required=True,
                min_length=1,
                max_length=4,
                value=str(self.question.max_length),
            )
        )

    async def process(self):
        errors = await super().process() or []
        try:
            minimum = int(self.children[2].value)
            if 0 <= minimum <= 4000:
                self.question.min_length = minimum
            else:
                errors.append("Minimum Length Needs To Be Between 0 And 4000")
        except ValueError:
            errors.append("Minimum Length Needs To Be A Number Between 0 And 4000. Do Not Use `,` Or `.`")

        try:
            maximum = int(self.children[3].value)
            if 1 <= maximum <= 4000:
                self.question.max_length = maximum
            else:
                errors.append("Maximum Length Needs To Be Between 1 And 4000")
        except ValueError:
            errors.append("Maximum Length Needs To Be A Number Between 1 And 4000. Do Not Use `,` Or `.`")

        return errors
