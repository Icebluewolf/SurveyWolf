from abc import ABC
import yaml

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
    def __init__(self, description=None, *args, **options):
        super().__init__(description=description, *args, **options)

        with open("config.yaml") as stream:
            config = yaml.safe_load(stream)

        self.ERROR_LOGGING_WEBHOOK = config["error_logging_webhook"]
        self.SERVER_JOIN_LEAVE_WEBHOOK = config["server_join_leave_webhook"]

    async def get_application_context(self, interaction: Interaction, cls=None) -> discord.ApplicationContext:
        return await super().get_application_context(interaction, cls=cls or AdvContext)
