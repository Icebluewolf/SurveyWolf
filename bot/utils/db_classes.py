import asyncpg
from datetime import datetime, timedelta

import discord

from utils.database import database as db


class QuestionType:
    text = 0
    multiple_choice = 1

    to_text = {text: "Text",
             multiple_choice: "Multiple Choice"}

class BaseQuestion:
    def __init__(self, text: str, qtype: int, position: int, required: int, qid: int, survey_id: int):
        self.text = text
        self.q_type = qtype
        self.pos = position
        self.required = required
        self.qid = qid
        self.survey_id = survey_id

    def __str__(self):
        return f"Question: {self.text}\nQuestion Type: {QuestionType.to_text[self.q_type]}\nRequired: {str(self.required)}"

    async def to_embed(self) -> discord.Embed:
        e = discord.Embed(title=f"Question {self.pos + 1}", description=self.text)
        e.add_field(name="Required", value=str(self.required))
        e.add_field(name="Question Type", value=QuestionType.to_text[self.q_type])
        e.add_field(name="Required", value=str(self.required))
        return e

class TextQuestion(BaseQuestion):
    def __init__(self, text: str, position: int, required: bool, qid: int = None, survey_id: int = None):
        super().__init__(text, QuestionType.text, position, required, qid, survey_id)

    async def to_embed(self) -> discord.Embed:
        return await super().to_embed()

    @classmethod
    async def from_db_row(cls, row: asyncpg.Record):
        return cls(
            text=row.get("text", None),
            position=row.get("position", None),
            required=row.get("required", None),
            survey_id=row.get("survey_id", None),
        )

class MCQuestion(BaseQuestion):
    def __init__(self, text: str, position: int, required: bool, options: list[str] = None,
                 min_choices: int = None, max_choices: int = None, q_id: int = None, survey_id: int = None):
        super().__init__(text, QuestionType.multiple_choice, position, required, q_id, survey_id)
        # Multiple Choice Question Info
        self.options: list[str] | None = options
        self.min_choices: int | None = min_choices
        self.max_choices: int | None = max_choices

    def __str__(self):
        op = '\n'.join(self.options)
        return (f"{super().__str__()}\n**Options:**\n {op}\n**Minimum Choices:** "
                f"{self.min_choices}    **Maximum Choices:** {self.max_choices}")

    async def to_embed(self) -> discord.Embed:
        e = await super().to_embed()
        e.add_field(name="Options", value="\n".join(self.options))
        e.add_field(name="Choices", value=f"Maximum: {self.max_choices}\nMinimum: {self.min_choices}")
        return e

    @classmethod
    async def from_db_row(cls, row: asyncpg.Record):
        return cls(
            text=row.get("text", None),
            position=row.get("position", None),
            required=row.get("required", None),
            q_id=row.get("id", None),
            survey_id=row.get("survey_id", None),
            options=row.get("options", None),
            min_choices=row.get("min_choices", None),
            max_choices=row.get("max_choices", None),
        )

class Survey:
    def __init__(self, s_id, guild_id, anonymous, editable, entries_per, total_entries, time_limit, name):
        self.id: int = s_id
        self.guild_id: int = guild_id
        self.anonymous: bool = anonymous
        self.editable: bool = editable
        self.entries_per: int = entries_per
        self.total_entries: int = total_entries
        self.time_limit: timedelta = time_limit
        self.name: str = name

    async def get_questions(self) -> list[BaseQuestion]:
        sql = """SELECT * FROM surveys.questions WHERE survey_id = $1"""
        rows = await db.fetch(sql, self.id)
        qs = await gather_questions(rows)
        qs.sort(key=lambda x: x.pos)
        return qs

    @classmethod
    async def from_db_row(cls, row: asyncpg.Record):
        try:
            s_id = row["template_id"]
        except KeyError:
            s_id = row["id"]
        return cls(
            s_id=s_id,
            guild_id=row["guild_id"],
            anonymous=row["anonymous"],
            editable=row["editable"],
            entries_per=row["entries_per"],
            total_entries=row["total_entries"],
            time_limit=row["time_limit"],
            name=row["name"],
        )


class ActiveSurvey:
    def __init__(self, as_id: int, end_date: datetime, template_id: int):
        self.id = as_id
        self.end_date = end_date
        self.template_id = template_id
        self.template: Survey | None = None

    @classmethod
    async def from_db_row(cls, row: asyncpg.Record):
        try:
            ags_id = row["ags_id"]
        except KeyError:
            ags_id = row["id"]
        return cls(
            as_id=ags_id,
            end_date=row["end_date"],
            template_id=row["template_id"],
        )

    async def get_template(self):
        if not self.template:
            sql = "SELECT * FROM surveys.guild_surveys WHERE id = $1;"
            result = await db.fetch(sql, self.template_id)
            self.template = await Survey.from_db_row(result[0])
        return self.template


class SurveyResponse:
    def __init__(self, sr_id: int, usr_id: int, q_id: int, response: str, r_num: int, as_id: int):
        self.id = sr_id
        self.user_id = usr_id
        self.question_id = q_id
        self.response = response
        self.response_num = r_num
        self.active_survey_id = as_id

    @classmethod
    async def from_db_row(cls, rows: asyncpg.Record | list[asyncpg.Record]):
        if type(rows) is not list:
            rows = [rows]

        result = []
        for row in rows:
            result.append(
                cls(
                    sr_id=row.get("id", None),
                    usr_id=row.get("user_id", None),
                    q_id=row.get("question_id", None),
                    response=row.get("response", None),
                    r_num=row.get("response_num", None),
                    as_id=row.get("active_survey_id", None),
                )
            )

        return result

async def gather_questions(rows: asyncpg.Record | list[asyncpg.Record]) -> list[BaseQuestion]:
    if not isinstance(rows, list):
        rows = [rows]
    result = []
    for row in rows:
        q_type = int(row.get("type"))
        if q_type == QuestionType.text:
            obj = await TextQuestion.from_db_row(row)
        elif q_type == QuestionType.multiple_choice:
            obj = await MCQuestion.from_db_row(row)
        else:
            raise ValueError(f"Unknown question type: {q_type}")
        result.append(obj)
    return result
