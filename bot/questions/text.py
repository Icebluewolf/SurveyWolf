import discord
from asyncpg import Record, Connection

from questions.input_text_response import InputTextResponse
from questions.survey_question import GetBaseInfo

from utils.database import database as db


class TextQuestion(InputTextResponse):

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

    @db.transactional
    async def save(self, *, conn: Connection) -> None:
        update = bool(self._id)
        await super().save(conn=conn)

        if update:
            sql = """UPDATE surveys.question_text SET min_length=$1, max_length=$2 WHERE id=$3;"""
            await conn.execute(sql, self.min_length, self.max_length, self._id)
        else:
            sql = """INSERT INTO surveys.question_text (min_length, max_length, id) VALUES ($1, $2, $3);"""
            await conn.execute(sql, self.min_length, self.max_length, self._id)

    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        m = GetTextQuestionInfo(self)
        await interaction.response.send_modal(m)
        await m.wait()
        return m.interaction

    @classmethod
    async def fetch(cls, id: int):
        sql = """
                SELECT * FROM surveys.questions 
                JOIN surveys.question_text qd ON questions.id = qd.id 
                WHERE questions.id=$1
            """
        return await cls.load(await db.fetch_one(sql, id))

    @classmethod
    @db.transactional
    async def fetch_by_template(cls, template_id: int, conn: Connection):
        sql = """
            SELECT * FROM surveys.questions JOIN surveys.question_text qd ON questions.id = qd.id
            WHERE questions.survey_id=$1;
        """
        return [await cls.load(x) for x in await conn.fetch(sql, template_id)]

    @db.transactional
    async def save_response(self, response_id: int, *, conn: Connection) -> int:
        resp = await super().save_response(conn=conn, response_id=response_id)
        sql = """INSERT INTO surveys.question_response_text (response, text) VALUES ($1, $2);"""
        await conn.execute(sql, resp, self.value)
        return resp

    @classmethod
    async def load(cls, row: Record):
        q = await super().load(row)
        q.min_length = row["min_length"]
        q.max_length = row["max_length"]
        return q

    @classmethod
    @db.transactional
    async def fetch_responses(cls, question_ids: list[int], *, conn: Connection) -> list[Record]:
        sql = """
            SELECT qr.id, qr.question, qr.response, qrt.text
            FROM surveys.question_response qr
                JOIN surveys.question_response_text qrt
                ON qrt.response = qr.id 
            WHERE qr.question = ANY($1::int[]);
        """
        return await conn.fetch(sql, question_ids)

    async def view_response(self, response: Record) -> str:
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
