from abc import ABC

import discord
from utils.database import database
from discord import Interaction


class AdvContext(discord.ApplicationContext):
    # For attributes of ctx
    # @property
    # def name(self):
    #     return "object"

    pass
    # @property
    # def db(self):
    #     return database

    # async def respond(self, *args, **kwargs) -> Interaction | WebhookMessage:
    #     return await super().respond(*args, **kwargs)


setattr(discord.ApplicationContext, "db", database)
setattr(discord.Interaction, "db", database)
setattr(discord.Bot, "db", database)


class SurveyWolf(discord.Bot, ABC):
    # def __init__(self, description=None, *args, **options):
    #     super().__init__(self, *args, **options)

    async def get_application_context(self, interaction: Interaction, cls=None) -> discord.ApplicationContext:
        return await super().get_application_context(interaction, cls=cls or AdvContext)
