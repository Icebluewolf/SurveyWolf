from abc import ABC
from enum import Enum
from datetime import timedelta, datetime
from asyncache import cached
from cachetools import LRUCache

import discord
from asyncpg import Record
from discord import InteractionType

from questions.input_text_response import InputTextResponse
from questions.survey_question import SurveyQuestion, from_db
from utils.database import database as db
from utils import embed_factory as ef


GUILD_TEMPLATE_CACHE = LRUCache(maxsize=128)
TEMPLATE_CACHE = LRUCache(maxsize=128)


class AnonymousType(Enum):
    private = 0
    public = 1
    protected = 2

    def __bool__(self):
        if self.value == AnonymousType.private:
            return True
        else:
            return False


class SurveyTemplate:
    def __init__(self, title: str, guild_id: int):
        self.questions: list[SurveyQuestion] = []
        self.title: str = title
        self.description: str = ""
        self.anonymous: AnonymousType = AnonymousType.private
        self.entries_per_user: int = 1
        self.duration: timedelta | None = None
        self.max_entries: int | None = None
        self.editable_responses: bool = False
        self.guild_id: int = guild_id
        self._id: int | None = None

    @staticmethod
    @cached(TEMPLATE_CACHE)
    async def fetch(id: int, with_questions: bool = True):
        sql = """SELECT * FROM surveys.template WHERE id=$1;"""
        row = await db.fetch_one(sql, id)
        template = await SurveyTemplate.load(row)

        if with_questions:
            await template.fill_questions()
        return template

    @classmethod
    async def load(cls, row: Record):
        template = cls(row["title"], row["guild_id"])
        template._id = row["id"]
        template.description = row["description"]
        template.anonymous = AnonymousType(row["anonymous"])
        template.entries_per_user = row["entries_per"]
        template.duration = row["time_limit"]
        template.max_entries = row["max_entries"]
        return template

    async def fill_questions(self, force=False):
        if not force and len(self.questions) > 0:
            return
        sql = """SELECT id, type FROM surveys.questions WHERE survey_id=$1;"""
        rows = await db.fetch(sql, self._id)
        self.questions = []
        for row in rows:
            self.questions.append(await from_db(row))

    @staticmethod
    async def check_exists(title: str, guild_id: int) -> bool:
        sql = """SELECT title FROM surveys.template WHERE title=$1 AND guild_id=$2 LIMIT 1;"""
        result = await db.fetch_one(sql, title, guild_id)
        return result is not None

    async def save(self) -> None:
        async with db.transaction() as conn:
            if self._id:
                sql = """
                UPDATE surveys.template 
                SET title=$2, description=$3, anonymous=$4, entries_per=$5, time_limit=$6, max_entries=$7, editable=$8
                WHERE id=$1;
                """
                await conn.execute(
                    sql,
                    self._id,
                    self.title,
                    self.description,
                    self.anonymous.value,
                    self.entries_per_user,
                    self.duration,
                    self.max_entries,
                    self.editable_responses,
                )
            else:
                sql = """
                INSERT INTO surveys.template 
                (guild_id, title, description, anonymous, entries_per, time_limit, max_entries, editable) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id;
                """
                self._id = await conn.fetchval(
                    sql,
                    self.guild_id,
                    self.title,
                    self.description,
                    self.anonymous.value,
                    self.entries_per_user,
                    self.duration,
                    self.max_entries,
                    self.editable_responses,
                )
                # Only Add It To The Cache If It Is New, As It Should Already Be In The Cache Otherwise
                GUILD_TEMPLATE_CACHE.setdefault(self.guild_id, []).append(self)

            for n, question in enumerate(self.questions):
                question.template = self._id
                question.position = n
                await question.save(n, conn)


    async def delete(self) -> None:
        sql = "DELETE FROM surveys.template WHERE guild_id=$1 AND id=$2;"
        await db.execute(sql, self.guild_id, self._id)
        try:
            GUILD_TEMPLATE_CACHE[self.guild_id].remove(self)
        except ValueError | KeyError:
            pass

    async def add_question(self, question: SurveyQuestion, pos: int) -> None:
        self.questions.insert(pos, question)

    async def summary(self, end: datetime) -> discord.Embed:
        e = discord.Embed(title=self.title, description=self.description)
        e.set_footer(text="Closes")
        e.timestamp = end
        e.add_field(
            name="General Information",
            value=f"""- Anonymous: {self.anonymous.name.capitalize()}
- Entries Per User: {self.entries_per_user}
- Can Edit Responses: {self.editable_responses}
{f"- Will Close Early If `{self.max_entries}` Entries Are Recorded" if self.max_entries else ""}
            """,
        )
        return e

    async def send_questions(
        self, interaction: discord.Interaction, encrypted_user_id: str, response_num: int, active_id: int
    ):
        input_text_group: list[InputTextResponse] = []
        for question in sorted(self.questions, key=lambda x: x.position):
            if isinstance(question, InputTextResponse):
                input_text_group.append(question)
                # If the group is full send it
                if len(input_text_group) == 5:
                    interaction = await do_modal_transition(interaction)
                    interaction = await question.send_question(interaction, input_text_group)
                    input_text_group = []
                continue

            # If the next question was not added to the group but there is pending questions in the group
            if len(input_text_group) > 0:
                interaction = await do_modal_transition(interaction)
                interaction = await input_text_group[-1].send_question(interaction, input_text_group)
                input_text_group = []

            interaction = await question.send_question(interaction)
        # There are no more questions but still questions pending in the group
        if len(input_text_group) > 0:
            interaction = await do_modal_transition(interaction)
            interaction = await input_text_group[-1].send_question(interaction, input_text_group)

        async with db.transaction() as conn:
            sql = """INSERT INTO surveys.responses (user_id, response_num, active_survey_id, template_id) 
                    VALUES ($1, $2, $3, $4) RETURNING id;"""
            response_id = await conn.fetchval(sql, encrypted_user_id, response_num, active_id, self._id)
            for question in self.questions:
                await question.save_response(conn, encrypted_user_id, response_num, active_id, response_id)
        await interaction.respond(embed=await ef.success("You Have Completed The Survey!"), ephemeral=True)


class ModalTransition(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.old_interaction = interaction
        self.new_interaction = None

    @discord.ui.button(label="Continue With The Survey")
    async def callback(self, button, interaction: discord.Interaction):
        self.new_interaction = interaction
        self.stop()

    async def send(self):
        e = await ef.general("To Continue Click The Button Below")
        await self.old_interaction.respond(ephemeral=True, view=self, embed=e)


async def do_modal_transition(interaction: discord.Interaction) -> discord.Interaction:
    if interaction.type != InteractionType.modal_submit:
        return interaction

    view = ModalTransition(interaction)
    await view.send()
    await view.wait()
    return view.new_interaction


async def title_autocomplete(ctx: discord.AutocompleteContext):
    match = []
    templates = await get_templates(ctx.interaction.guild_id)
    for template in templates:
        if template.title.startswith(ctx.value):
            match.append(discord.OptionChoice(name=template.title, value=str(template._id)))
            if len(match) == 24:
                break
    return match


async def get_templates(guild_id: int) -> list[SurveyTemplate]:
    try:
        return GUILD_TEMPLATE_CACHE[guild_id]
    except KeyError:
        sql = """SELECT * FROM surveys.template WHERE guild_id=$1;"""
        rows = await db.fetch(sql, guild_id)
        GUILD_TEMPLATE_CACHE[guild_id] = [await SurveyTemplate.load(x) for x in rows]
        return GUILD_TEMPLATE_CACHE[guild_id]
