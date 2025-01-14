from discord import Cog, slash_command, Option, ApplicationContext

from forms.survey.active import ActiveSurvey, load_active_surveys
from forms.survey.template import title_autocomplete, get_templates
from utils.timers import Timer
from utils import embed_factory as ef


class ActiveSurveyCommands(Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command()
    async def send(
        self,
        ctx: ApplicationContext,
        name: Option(str, autocomplete=title_autocomplete, description="The Survey Template To Send"),
        message: Option(str, description="A Message To Accompany The Survey", required=False, default=None),
        duration_override: Option(
            str, description="An Override For The Default Time Of The Template", required=False, default=None
        ),
    ):
        if duration_override:
            duration_override = Timer.str_time(duration_override)
            if duration_override.total_seconds() == 0:
                return await ctx.respond(
                    embed=await ef.fail(
                        """You Entered A Value For `Duration Override` But It Was Not Valid. 
                        You Should Write The Time In This Format: `2 hours and 15 minutes`.
                        Abbreviations Like `min` Or `m` For Minutes Are Also Allowed."""
                    )
                )

        templates = await get_templates(ctx.guild_id)
        for template in templates:
            if name == str(template._id) or name == template.title:
                break
        else:
            return await ctx.respond(embed=await ef.fail(f"No Survey Named `{name}` Found"), ephemeral=True)
        if template.duration is None and duration_override is None:
            return await ctx.respond(
                embed=await ef.fail(
                    "You Must Set A `duration_override` If The Survey Does Not Have A Default Duration"
                ),
                ephemeral=True,
            )
        survey = ActiveSurvey(template, duration_override)
        await survey.save()
        await ctx.interaction.respond(embed=await ef.success("The Survey Was Started"), ephemeral=True)
        await survey.send(ctx.interaction, message)

    @Cog.listener(once=True)
    async def on_ready(self):
        for view in await load_active_surveys():
            self.bot.add_view(view)


def setup(bot):
    bot.add_cog(ActiveSurveyCommands(bot))
