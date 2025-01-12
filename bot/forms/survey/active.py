from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import discord
from asyncpg import Record

from forms.survey.template import SurveyTemplate
from utils.database import database as db
from utils import embed_factory as ef
from utils.timers import Timer
from utils.utils import encrypt_id


class ActiveSurvey:
    def __init__(self, template: int | SurveyTemplate, end: datetime | timedelta | None = None):
        self.template: int | SurveyTemplate = template
        if end is None:
            self.end = datetime.now() + template.duration
        elif isinstance(end, datetime):
            self.end = end
        elif isinstance(end, timedelta):
            self.end = datetime.now() + end
        self._channel_id = None
        self._message_id = None
        self._id = None
        self._timer: Timer | None = None

    @classmethod
    async def load(cls, row: Record):
        c = cls(row["template_id"], row["end_date"])
        c._id = row["id"]
        c._channel_id = row["channel_id"]
        c._message_id = row["message_id"]
        return c

    @classmethod
    async def fetch(cls, id: int):
        sql = """SELECT end_date, template_id, channel_id, message_id FROM surveys.active_guild_surveys WHERE id=$1"""
        row = await db.fetch_one(sql, id)
        return cls.load(row)

    async def save(self):
        sql = """
        INSERT INTO surveys.active_guild_surveys (end_date, template_id, channel_id, message_id) 
        VALUES ($1, $2, $3, $4) RETURNING id;
        """
        if isinstance(self.template, SurveyTemplate):
            template = self.template._id
        else:
            template = self.template
        self._id = await db.fetchval(sql, self.end, template, self._channel_id, self._message_id)

    async def send(self, interaction: discord.Interaction, message: str):
        v = ActiveSurveyView(self)
        await interaction.followup.send(
            embeds=[await ef.general("Take The Survey Below!", message=message), await self.template.summary(self.end)],
            view=v,
        )
        await self.start_timer(v.end_survey)

    async def start_timer(self, callback):
        self._timer = Timer(self.end, callback)

    async def end_survey(self):
        # Expired Surveys Should Just No Longer Be Loaded. No Need To Remove Them
        # sql = """DELETE FROM surveys.active_guild_surveys WHERE id=$1"""
        # await db.execute(sql, self._id)
        await self._timer.cancel()


class ActiveSurveyView(discord.ui.View):
    def __init__(self, survey: ActiveSurvey):
        super().__init__(timeout=None)
        self.survey = survey
        self.add_item(SurveyButton(survey._id))

    async def end_survey(self):
        await self.survey.end_survey()
        self.disable_all_items()
        await self.message.edit(embeds=[await ef.general("This Survey Has Ended"), self.message.embeds[1]], view=self)
        self.stop()


class SurveyButton(discord.ui.Button):
    def __init__(self, custom_id: int):
        super().__init__(label="Take Survey", style=discord.ButtonStyle.blurple, custom_id=str(custom_id))
        self.encrypted_user_id: str | None = None

    async def callback(self, interaction: discord.Interaction):
        # await interaction.response.defer()
        template = self.view.survey.template

        # Check If Time Is Up On The Survey
        if self.view.survey.end and self.view.survey.end < datetime.now():
            await self.view.end_survey()
            return await interaction.respond(embed=await ef.fail("Sorry! This Survey Has Ended"), ephemeral=True)

        # Get The Encrypted User ID
        self.encrypted_user_id = await encrypt_id(interaction.user.id)

        # Fetch The Template If Needed
        if isinstance(template, int):
            self.view.survey.template = await SurveyTemplate.fetch(template, True)
            template = self.view.survey.template
        else:
            await template.fill_questions()

        # Check If The User Has Responded To The Survey The Maximum Number Of Times
        sql = """SELECT DISTINCT max(response_num) FROM surveys.responses 
                WHERE user_id=$2 and active_survey_id = $1;"""
        times_taken = await db.fetchval(sql, int(self.view.survey._id), self.encrypted_user_id)
        if times_taken is None:
            times_taken = 0
        if times_taken >= template.entries_per_user:
            return await interaction.respond(
                embed=await ef.fail(
                    f"You Have Taken The Survey The Maximum Amount Of Times (`{template.entries_per_user}`)"
                ),
                ephemeral=True,
            )

        # Check If The Maximum Number Of Survey Responses Has Been Reached
        if template.max_entries is not None:
            sql = """SELECT COUNT(*) FROM surveys.responses WHERE active_survey_id = $1 
            GROUP BY user_id, response_num;"""
            total_responses = await db.fetchval(sql, self.view.survey._id)
            if total_responses > template.max_entries:
                await self.view.end_survey()
                return await interaction.respond(
                    embed=await ef.fail("Sorry! This Survey Has Reached The Maximum Amount Of Entries"), ephemeral=True
                )

        # Finally Send The Survey
        await self.view.survey.template.send_questions(
            interaction, self.encrypted_user_id, times_taken + 1, self.view.survey._id
        )

    if TYPE_CHECKING:

        @property
        def view(self) -> ActiveSurveyView:
            pass


async def load_active_surveys():
    sql = """SELECT id, end_date, template_id, channel_id, message_id FROM surveys.active_guild_surveys
    WHERE end_date > NOW();"""
    rows = await db.fetch(sql)
    views = []
    for row in rows:
        s = await ActiveSurvey.load(row)
        v = ActiveSurveyView(s)
        await s.start_timer(v.end_survey)
        views.append(v)
    return views
