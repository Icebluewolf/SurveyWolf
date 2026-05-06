from collections import defaultdict

import discord
from asyncpg import Record, Connection

from abc import ABC, abstractmethod
from enum import Enum

from utils import embed_factory as ef
from utils.database import database as db

# Lazy Imports Are Being Used In `question_maps`


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
    @abstractmethod
    async def fetch(cls, id: int):
        """
        Gets The Question From The Database By ID
        :param id: The ID of the question
        :return: An instance of the class it is called on
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    @db.transactional
    async def fetch_by_template(cls, template_id: int, conn: Connection):
        """
        Gets All Questions From The Database Associated With The Given Template
        :param template_id: The Template ID to fetch questions from
        :param conn: The database connection
        :return: A list of all questions of this type associated with the template
        """
        raise NotImplementedError

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
    async def display(self) -> discord.Embed:
        """
        An Embed That Displays All The Details Of The Question
        :return: The created Embed
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
    @db.transactional
    async def save(self, *, conn: Connection) -> None:
        """
        Save The Question To The Database
        :param conn: Connection to use. Useful for batching requests
        """
        if self._id:
            sql = """UPDATE surveys.questions SET text=$1, position=$2, required=$3, description=$4 WHERE id=$5;"""
            await conn.execute(sql, self.title, self.position, self.required, self.description, self._id)
        else:
            sql = """INSERT INTO surveys.questions (text, position, survey_id, required, description, type) 
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id;"""
            record = await conn.fetch(sql, self.title, self.position, self.template, self.required, self.description, question_maps()[1][self.__class__].value)
            self._id = record[0]["id"]

    @db.transactional
    async def delete(self, *, conn: Connection) -> None:
        """
        Deletes The Question From The Database
        The deletion should cascade to the question specific tables so this method does not need to be overridden
        """
        if self._id is None:
            raise AttributeError("Cannot delete a question without an ID")

        sql = """DELETE FROM surveys.questions WHERE id=$1;"""
        await conn.execute(sql, self._id)

    @abstractmethod
    @db.transactional
    async def save_response(self, response_id: int, *, conn: Connection) -> int:
        """
        Saves The Users Response To This Question To The Database
        :param conn: The Database connection to use. Useful for batching requests
        :param response_id: The ID of the main response row
        :return The Response ID
        """
        sql = """INSERT INTO surveys.question_response (response, question) VALUES ($1, $2) RETURNING id;"""
        return await conn.fetchval(sql, response_id, self._id)

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

    @classmethod
    @abstractmethod
    @db.transactional
    async def fetch_responses(cls, question_ids: list[int], *, conn: Connection) -> list[Record]:
        """
        Fetch the responses for the given Question IDs.
        The Question IDs must match the type of question the operation is being executed on.
        :param question_ids: A list of question IDs corresponding to questions of the type
        :param conn: The database connection
        :return: A list of Records in the corresponding question types format.
        """
        raise NotImplementedError

    @abstractmethod
    async def view_response(self, response: Record) -> str:
        """
        A Short String Representation Of The Response To The Question
        :param response: The Record From The Question Specific Response Data
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
                embed=await ef.fail("\n".join(errors)),
                ephemeral=True,
            )


class QuestionType(Enum):
    TEXT = 0
    MULTIPLE_CHOICE = 1
    DATETIME = 2


def question_maps():
    from questions.text import TextQuestion
    from questions.multiple_choice import MultipleChoice
    from questions.datetime import DateQuestion
    question_cls: dict[QuestionType, type[SurveyQuestion]] = {
            QuestionType.TEXT: TextQuestion,
            QuestionType.MULTIPLE_CHOICE: MultipleChoice,
            QuestionType.DATETIME: DateQuestion,
        }
    cls_question: dict[type[SurveyQuestion], QuestionType] = {v: k for k, v in question_cls.items()}
    return question_cls, cls_question


async def from_db(row: Record) -> SurveyQuestion:
    return await question_maps()[0][QuestionType(row["type"])].fetch(row["id"])


async def fetch_template_questions(template_id: int) -> list[SurveyQuestion]:
    result = []
    for q_type in question_maps()[0].values():
        result.extend(await q_type.fetch_by_template(template_id))
    return result


async def fetch_question_responses(questions: list[SurveyQuestion]) -> list[Record]:
    d = defaultdict(list)
    for q in questions:
        d[type(q)].append(q._id)

    result = []
    for q_type, ques in d.items():
        result.extend(await q_type.fetch_responses(ques))
    return result
