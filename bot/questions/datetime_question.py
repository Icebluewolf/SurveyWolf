import datetime
import warnings
from enum import Enum
from typing import TYPE_CHECKING, Self

import discord
from asyncpg import Connection, Record
from discord import Interaction
from dateutil.parser import parse as datetime_parser, ParserError, UnknownTimezoneWarning

from questions.input_text_response import InputTextResponse, GetResponse
from questions.survey_question import QuestionType, GetBaseInfo
from utils.embed_factory import general
from utils.database import database as db
from utils.timers import Timer


class DateQuestionType(Enum):
    DATETIME = 0
    DATE = 1
    TIME = 2
    DURATION = 3

    def human_readable(self) -> str:
        if self.value == DateQuestionType.DATETIME.value:
            return "Date And Time"
        elif self.value == DateQuestionType.TIME.value:
            return "Time"
        elif self.value == DateQuestionType.DURATION.value:
            return "Duration"
        elif self.value == DateQuestionType.DATE.value:
            return "Date"
        else:
            raise TypeError("value must be of type DateQuestionType")


class DateQuestion(InputTextResponse):
    QUESTION_TYPE = QuestionType.DATETIME

    def __init__(self, title: str, survey_id: int):
        # This constructor is meant for creating new questions
        super().__init__(title, survey_id)
        self.description: str = ""
        self.required = True
        self._id = None

        self.value: datetime.datetime | datetime.time | datetime.timedelta | datetime.date | None = None
        self.type: DateQuestionType = DateQuestionType.DATETIME
        self.minimum: datetime.datetime | datetime.time | datetime.timedelta | datetime.date | None = None
        self.maximum: datetime.datetime | datetime.time | datetime.timedelta | datetime.date | None = None

    async def set_up(self, interaction: discord.Interaction) -> discord.Interaction:
        m = GetBaseInfo(self, self.title)
        await interaction.response.send_modal(m)
        await m.wait()
        interaction = m.interaction
        v = Settings(self)
        await interaction.response.edit_message(view=v, embed=await self.display())
        if not await v.wait():
            return v.interaction

    async def send_question(self, interaction: discord.Interaction, group: list[Self] = None) -> discord.Interaction:
        modal = GetResponse(group or [self])
        await interaction.response.send_modal(modal)
        await modal.wait()
        return modal.interaction

    async def display(self) -> discord.Embed:
        e = await general(title=self.title, message=self.description + "\n\nFormat: " + self.type.human_readable())

        e.description += f"\nMinimum: {await self._get_discord_format(self.minimum)}"
        e.description += f"\nMaximum: {await self._get_discord_format(self.maximum)}"
        return e

    async def short_display(self) -> str:
        return f"{self.title} {self.description}\n\nFormat: {self.type.human_readable()}"

    async def _get_storable_format(self, obj: datetime.datetime | datetime.time | datetime.timedelta | datetime.date) -> str:
        if obj is None:
            return ""
        if self.type == DateQuestionType.DATETIME:
            timestamp = obj.timestamp()
        elif self.type == DateQuestionType.TIME or self.type == DateQuestionType.DATE:
            timestamp = obj.isoformat()
        elif self.type == DateQuestionType.DURATION:
            timestamp = obj.total_seconds()
        else:
            raise TypeError("value must be of type DateQuestionType")
        return str(timestamp)

    async def _get_discord_format(self, obj: datetime.datetime | datetime.time | datetime.timedelta | datetime.date | None) -> str:
        if obj is None:
            return "None"
        if self.type == DateQuestionType.DATETIME:
            timestamp = discord.utils.format_dt(obj, "F")
        elif self.type == DateQuestionType.DATE:
            timestamp = discord.utils.format_dt(datetime.datetime.combine(obj, datetime.datetime.min.time()), "D")
        elif self.type == DateQuestionType.TIME:
            timestamp = discord.utils.format_dt(datetime.datetime.combine(datetime.datetime.now(datetime.UTC).date(), obj), "T")
        elif self.type == DateQuestionType.DURATION:
            timestamp = str(obj)
        else:
            raise TypeError("value must be of type DateQuestionType")
        return str(timestamp)

    def prompt_user_format(self) -> str:
        if self.type == DateQuestionType.DATE:
            placeholder = "Enter In The Format Day/Month/Year"
        elif self.type == DateQuestionType.TIME:
            placeholder = "Enter In The Format 24Hour:Minute:Second Timezone With UTC Being The Default"
        elif self.type == DateQuestionType.DATETIME:
            placeholder = "Enter In The Format Day/Month/Year 24Hour:Minute:Second Timezone With UTC Being The Default"
        elif self.type == DateQuestionType.DURATION:
            placeholder = "Enter In The Format 2 hours and 15 minutes. Abbreviations Like min Or m For Are Also Allowed"
        else:
            placeholder = ""
        return placeholder

    async def _from_storable_format(self, timestamp: str) -> datetime.datetime | datetime.time | datetime.timedelta | datetime.date | None:
        if timestamp == "":
            return None
        if self.type == DateQuestionType.DATETIME:
            obj = datetime.datetime.fromtimestamp(float(timestamp))
        elif self.type == DateQuestionType.DATE:
            obj = datetime.date.fromisoformat(timestamp)
        elif self.type == DateQuestionType.TIME:
            obj = datetime.time.fromisoformat(timestamp)
        elif self.type == DateQuestionType.DURATION:
            obj = datetime.timedelta(seconds=float(timestamp))
        else:
            raise TypeError("value must be of type DateQuestionType")
        return obj

    async def _create_data(self) -> dict:
        return {
            "type": self.type.value,
            "minimum": await self._get_storable_format(self.minimum),
            "maximum": await self._get_storable_format(self.maximum),
        }

    async def _create_response_data(self) -> dict:
        timestamp = await self._get_storable_format(self.value)
        return {
            "timestamp": timestamp,
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
                DateQuestion.QUESTION_TYPE.value,
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
                DateQuestion.QUESTION_TYPE.value,
                await self._create_data(),
            )
            self._id = record[0]["id"]

    @classmethod
    async def load(cls, row: Record):
        q = await super().load(row)
        q.type = DateQuestionType(row["question_data"]["type"])
        q.minimum = await cls._from_storable_format(q, row["question_data"]["minimum"])
        q.maximum = await cls._from_storable_format(q, row["question_data"]["maximum"])
        return q

    async def delete(self) -> None:
        sql = """DELETE FROM surveys.questions WHERE id=$1;"""
        await db.execute(sql, self._id)

    async def save_response(self, conn: Connection, encrypted_user_id: str, active_id: int, response_id: int) -> None:
        sql = """INSERT INTO surveys.question_response (response, question, response_data) VALUES ($1, $2, $3);"""
        await conn.execute(sql, response_id, self._id, await self._create_response_data())

    async def view_response(self, response: dict) -> str:
        return await self._get_discord_format(await self._from_storable_format(response["timestamp"]))

    def get_input_text(self) -> discord.ui.InputText:
        return discord.ui.InputText(
            label=self.title[: min(len(self.title), 45)],
            required=self.required,
            style=discord.InputTextStyle.long,
            placeholder=self.prompt_user_format(),
        )

    async def handle_input_text_response(self, text: str) -> str | None:
        if text is None:
            self.value = None
            return None
        converted = None
        try:
            with warnings.catch_warnings(category=UnknownTimezoneWarning, action="error"):
                if self.type == DateQuestionType.DATE:
                    converted = datetime_parser(text, dayfirst=True, yearfirst=False).date()
                elif self.type == DateQuestionType.TIME:
                    t = datetime_parser(text,
                                        dayfirst=True,
                                        yearfirst=False,
                                        default=datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                                        ).timetz()
                    converted = t
                elif self.type == DateQuestionType.DATETIME:
                    t = datetime_parser(text,
                                        dayfirst=True,
                                        yearfirst=False,
                                        default=datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                                        )
                    converted = t
                elif self.type == DateQuestionType.DURATION:
                    delta = Timer.str_time(text)
                    if delta.total_seconds() == 0:
                        raise ParserError("Duration Did Not Find Any Valid Units")
                    converted = delta
        except ParserError as e:
            return f"Could Not Convert Question {self.position + 1} To A {self.type.human_readable()}: {str(e)}"
        except UnknownTimezoneWarning:
            return f"A Timezone Was Provided But Not Understood For Question {self.position + 1}"
        except OverflowError:
            return f"The Value `{text}` Is Too Large To Be Interpreted For Question {self.position + 1}"

        if (self.minimum and converted < self.minimum) or (self.maximum and converted > self.maximum):
            if self.minimum and self.maximum:
                return f"The Value `{text}` Must Be In The Range {await self._get_discord_format(self.minimum)} to {await self._get_discord_format(self.maximum)}"

            limit_type = "Larger" if self.minimum else "Smaller"
            limit_value = await self._get_discord_format(self.minimum or self.maximum)
            return f"The Value `{text}` Must Be {limit_type} Than {limit_value}"

        # If it got past all the checks assign it to the value
        self.value = converted


class Settings(discord.ui.View):
    interaction: discord.Interaction

    def __init__(self, question: DateQuestion):
        super().__init__()
        self.question = question
        self.selected: discord.ui.Button | None = None
        self.pending_min: str = ""
        self.pending_max: str = ""
        for i in DateQuestionType:
            b = TypeButton(i.human_readable(), i)
            if self.question.type == i:
                self.selected = b
                b.disabled = True
                b.style = discord.ButtonStyle.green
                self.set_min_max.disabled = False
                self.finish.disabled = False
            self.add_item(b)

    async def update(self, interaction: discord.Interaction):
        if self.selected is not None:
            self.set_min_max.disabled = False
            self.finish.disabled = False
        await interaction.response.edit_message(view=self, embed=await self.question.display())

    @discord.ui.button(label="Set Min/Max", disabled=True, style=discord.ButtonStyle.gray, row=2)
    async def set_min_max(self, button, interaction: discord.Interaction):
        await interaction.response.send_modal(MinMaxModal(self.question, self, self.pending_min, self.pending_max))

    @discord.ui.button(label="Finish", disabled=True, style=discord.ButtonStyle.gray, row=2)
    async def finish(self, button, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()


class TypeButton(discord.ui.Button):
    def __init__(self, label: str, date_type: DateQuestionType):
        super().__init__(style=discord.ButtonStyle.blurple, label=label)
        self.date_type = date_type

    if TYPE_CHECKING:
        @property
        def view(self) -> Settings: ...

    async def callback(self, interaction: Interaction):
        if self.view.selected is not None:
            self.view.selected.style = discord.ButtonStyle.blurple
            self.view.selected.disabled = False

        self.view.question.type = self.date_type
        self.style = discord.ButtonStyle.green
        self.disabled = True
        self.view.selected = self
        # Ensure That The Min/Max Get Reset When A Different Type Is Selected So There Is Not A Mismatch In Types
        self.view.question.minimum = None
        self.view.question.maximum = None
        self.view.pending_min = ""
        self.view.pending_max = ""
        await self.view.update(interaction)


class MinMaxModal(discord.ui.Modal):
    def __init__(self, question: DateQuestion, view: Settings, minimum: str, maximum: str):
        super().__init__(title="Enter Minimum And Maximum Values")
        self.q = question
        self.view = view

        placeholder = self.q.prompt_user_format()

        self.add_item(discord.ui.InputText(label="Minimum", placeholder=placeholder, required=False, style=discord.InputTextStyle.long, value=minimum))
        self.add_item(discord.ui.InputText(label="Maximum", placeholder=placeholder, required=False, style=discord.InputTextStyle.long, value=maximum))

    async def callback(self, interaction: Interaction):
        formated = []
        errors = []
        for child in self.children:
            if child.label == "Minimum":
                self.view.pending_min = child.value
            elif child.label == "Maximum":
                self.view.pending_max = child.value

            if child.value.strip() == "":
                formated.append(None)
                continue
            try:
                if self.q.type == DateQuestionType.DATE:
                    formated.append(datetime_parser(child.value, dayfirst=True, yearfirst=False).date())
                elif self.q.type == DateQuestionType.TIME:
                    t = datetime_parser(child.value,
                                        dayfirst=True,
                                        yearfirst=False,
                                        default=datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                                        ).timetz()
                    formated.append(t)
                elif self.q.type == DateQuestionType.DATETIME:
                    t = datetime_parser(child.value,
                                        dayfirst=True,
                                        yearfirst=False,
                                        default=datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                                        )
                    formated.append(t)
                elif self.q.type == DateQuestionType.DURATION:
                    delta = Timer.str_time(child.value)
                    if delta.total_seconds() == 0:
                        raise ParserError("Duration Did Not Find Any Valid Units")
                    formated.append(delta)
            except ParserError as e:
                print(e)
                formated.append(None)
                errors.append(f"Could Not Convert `{child.value}` To A {self.q.type.human_readable()} Format")
            except OverflowError:
                formated.append(None)
                errors.append(f"The Value `{child.value}` Is Too Large")
        min_dt, max_dt = formated
        if not (min_dt is None or max_dt is None) and min_dt > max_dt:
            errors.append(f"The Minimum {self.q.type.human_readable()} Cannot Be Larger Than The Maximum")
        else:
            # Only Set These If They Are Valid
            # If They Were Not Successfully Converted They Are Set To None
            self.q.minimum = min_dt
            self.q.maximum = max_dt

        await self.view.update(interaction)
        if errors:
            em = discord.Embed(
                title="Some Settings Failed",
                description="Below Are The Errors Of The Settings That Were Not Inputted Correctly. If "
                            "There Is Not An Error The Setting Was Successfully Set.",
                color=0xD33033,
            )
            em.add_field(name="Errors", value="\n".join(errors))
            await interaction.followup.send(embed=em)
