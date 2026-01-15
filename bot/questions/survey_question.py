import discord
from asyncpg import Record, Connection

from abc import ABC, abstractmethod
from enum import Enum

from utils import component_factory as cf
from utils.database import database as db

# Use Of Lazy Imports In The `from_db` Function


class QuestionType(Enum):
    TEXT = 0
    MULTIPLE_CHOICE = 1
    DATETIME = 2


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
        """
        Gets The Question From The Database By ID
        :param id: The ID of the question
        :return: An instance of the class it is called on
        """
        sql = """
                SELECT text, questions.id, position, survey_id, required, description, type, question_data 
                FROM surveys.questions
                WHERE questions.id=$1;"""
        return await cls.load(await db.fetch_one(sql, id))

    @abstractmethod
    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        """
        Gathers User Input For The Settings Of The Question
        :param interaction: The interaction that is pending a response from the prior action
        :return: An interaction with no response to be used by the next action
        """
        raise NotImplementedError

    @abstractmethod
    async def send_question(self, interaction: discord.Interaction) -> discord.Interaction:
        """
        Sends The Question To A User Taking The Survey And Gathers The Response
        :param interaction: The interaction that is pending a response from the prior action
        :return: An interaction with no response to be used by the next action
        """
        raise NotImplementedError

    @abstractmethod
    async def display(self) -> discord.ui.Container:
        """
        A Container That Displays All The Details Of The Question
        :return: The created Container
        """
        raise NotImplementedError

    @abstractmethod
    async def short_display(self) -> str:
        """
        A Single Line String Containing The Most Important Information About The Question
        :return: A single line string
        """
        raise NotImplementedError

    @abstractmethod
    async def _create_data(self) -> dict:
        """
        Creates The JSONB Data For The Question To Be Inserted Into The Questions Table Of The Database
        :return: A dict that is converted to string by asyncpg
        """
        raise NotImplementedError

    @abstractmethod
    async def _create_response_data(self) -> dict:
        """
        Creates The JSONB Data For The Response To The Question To Be Inserted Into The Responses Table Of The Database
        :return: A dict that is converted to string by asyncpg
        """
        raise NotImplementedError

    @abstractmethod
    async def save(self, position: int, conn: Connection = None) -> None:
        """
        Save The Question To The Database
        :param position: The position of the question in the ordered list of questions
        :param conn: The database connection to use. Useful for batching requests
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self) -> None:
        """
        Deletes The Question From The Database
        """
        raise NotImplementedError

    @abstractmethod
    async def save_response(self, conn: Connection, encrypted_user_id: str, active_id: int, response_id: int) -> None:
        """
        Saves The Users Response To This Question To The Database
        :param conn: The Database connection to use. Useful for batching requests
        :param encrypted_user_id: The user ID of the user that submitted the answer
        :param active_id: The ID of the survey
        :param response_id: The ID of the main response row
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def load(cls, row: Record):
        """
        Create An Instance Of A SurveyQuestion From A Database Row
        :param row: The row retrieved from the database
        """
        q = cls(row["text"], row["survey_id"])
        q.position = row["position"]
        q.required = row["required"]
        q.description = row["description"]
        q._id = row["id"]
        return q

    @abstractmethod
    async def view_response(self, response: dict) -> str:
        """
        A Short String Representation Of The Response To The Question
        :param response: The JSONB response data column from the question response row
        :return: A string representation of the questions response
        """
        raise NotImplementedError


class GetBaseInfo(discord.ui.Modal):
    interaction: discord.Interaction

    def __init__(self, question: SurveyQuestion, title: str, *args, **kwargs):
        super().__init__(title=title, *args, **kwargs)
        self.question = question

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
            await interaction.followup.send(
                view=discord.ui.View(await cf.fail("\n".join(errors)), timeout=0),
                ephemeral=True,
            )


async def from_db(row) -> SurveyQuestion:
    if row["type"] == QuestionType.TEXT.value:
        from questions.text_question import TextQuestion

        return await TextQuestion.fetch(row["id"])
    elif row["type"] == QuestionType.MULTIPLE_CHOICE.value:
        from questions.multiple_choice import MultipleChoice

        return await MultipleChoice.fetch(row["id"])
    elif row["type"] == QuestionType.DATETIME.value:
        from questions.datetime_question import DateQuestion

        return await DateQuestion.fetch(row["id"])
