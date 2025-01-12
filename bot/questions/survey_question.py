import discord
from asyncpg import Record, Connection

from abc import ABC, abstractmethod
from enum import Enum

from utils import embed_factory as ef
from utils.database import database as db

# Use Of Lazy Imports In The `from_db` Function


class QuestionType(Enum):
    TEXT = 0
    MULTIPLE_CHOICE = 1


class SurveyQuestion(ABC):
    """
    An abstract representation of a base survey question

    Attributes
    ----------
    title: str
        The content of the question, most likely a question.
    description: str
        Any additional context for the question.
    required: bool
        If the question is allowed to be submitted without a response.
    template: int
        The template that the question belongs to.
    position: int
        The position the question should be placed at when sorting
    """

    title: str
    description: str
    required: bool
    template: int  # The ID of the template, nothing else should be needed
    position: int
    _id: int | None = None  # The PK Of The Question

    def __init__(self, title: str, template_id: int):
        self.title = title
        self.template = template_id

    @classmethod
    async def fetch(cls, id: int):
        sql = """
                SELECT text, questions.id, position, survey_id, required, description, type, question_data 
                FROM surveys.questions
                WHERE questions.id=$1;"""
        return await cls.load(await db.fetch_one(sql, id))

    @abstractmethod
    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        raise NotImplementedError

    @abstractmethod
    async def send_question(self, interaction: discord.Interaction) -> discord.Interaction:
        raise NotImplementedError

    @abstractmethod
    async def display(self) -> discord.Embed:
        raise NotImplementedError

    @abstractmethod
    async def short_display(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _create_data(self) -> dict:
        """Return A Dict That Is Converted To String By asyncpg"""
        raise NotImplementedError

    @abstractmethod
    async def _create_response_data(self) -> dict:
        """Return A Dict That Is Converted To String By asyncpg"""
        raise NotImplementedError

    @abstractmethod
    async def save(self, position: int, conn: Connection = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_response(
        self, conn: Connection, encrypted_user_id: str, response_num: int, active_id: int, response_id: int
    ) -> None:
        raise NotImplementedError

    @classmethod
    async def load(cls, row: Record):
        q = cls(row["text"], row["survey_id"])
        q.position = row["position"]
        q.required = row["required"]
        q.description = row["description"]
        q._id = row["id"]
        return q

    @staticmethod
    @abstractmethod
    async def view_response(response: dict) -> str:
        raise NotImplementedError


class GetBaseInfo(discord.ui.Modal):
    def __init__(self, question: SurveyQuestion, title: str, *args, **kwargs):
        super().__init__(title=title, *args, **kwargs)
        self.question = question
        self.interaction = None

        self.add_item(
            discord.ui.InputText(
                label="Question Text",
                required=True,
                min_length=1,
                max_length=1000,
                value=self.question.title,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Required",
                required=True,
                max_length=1,
                placeholder='"t" (true) or "f" (false)',
                value=("t" if self.question.required else "f"),
            )
        )

    async def process(self) -> list[str] | None:
        """Handles The Base Questions Returns A List Of Errors"""
        self.question.title = self.children[0].value
        if self.children[1].value.lower() == "t":
            self.question.required = True
        elif self.children[1].value.lower() == "f":
            self.question.required = False
        else:
            return ['Required Needs To Be Either "t" (True) Or "f" (False)']

    async def callback(self, interaction: discord.Interaction):
        # This interaction is grabbed and used by the thing that sent the modal
        self.interaction = interaction
        self.stop()
        errors = await self.process()
        if errors:
            await interaction.followup.send_message(
                embed=await ef.fail("\n".join(errors)),
                ephemeral=True,
            )


async def from_db(row) -> SurveyQuestion:
    if row["type"] == QuestionType.TEXT.value:
        from questions.text_question import TextQuestion

        return await TextQuestion.fetch(row["id"])
