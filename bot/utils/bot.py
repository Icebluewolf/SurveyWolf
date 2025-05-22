import traceback
from abc import ABC
from typing import Any

import yaml

import discord
from utils.database import database
from . import embed_factory as ef
from discord import Interaction, ApplicationContext, DiscordException


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
        self._did_on_ready = False

        with open("config.yaml") as stream:
            config = yaml.safe_load(stream)

        self._raw_config = config
        self.config = self._raw_config.copy()

    async def on_ready(self):
        if self._did_on_ready:
            return
        self._did_on_ready = True
        # Do Some Additional Processing On Some Config Items
        self.config.update(
            {
                "error_logging_webhook": await self._create_webhook(self.config["error_logging_webhook"]),
                "server_join_leave_webhook": await self._create_webhook(self.config["server_join_leave_webhook"]),
            }
        )

    async def _create_webhook(self, url: str) -> discord.Webhook | None:
        if url == "None":
            return None

        try:
            return await self.fetch_webhook(discord.Webhook.from_url(url, session=self.http._HTTPClient__session).id)
        except discord.NotFound:
            return None

    def update_config(self, key: str, value, raw=None) -> None:
        """
        Updates the config with the key and value. Updates the config file with the raw value
        :param key: The Config Key
        :param value: The Value The Bot Should Retrieve
        :param raw: The Value That Should Be Stored In The Config File. Defaults To `value`
        """
        if raw is None:
            raw = value

        self._raw_config[key] = raw
        with open("config.yaml", "w") as stream:
            yaml.safe_dump(self._raw_config, stream)
        self.config[key] = value

    async def get_application_context(self, interaction: Interaction, cls=None) -> discord.ApplicationContext:
        return await super().get_application_context(interaction, cls=cls or AdvContext)

    @staticmethod
    def _split_text(text: str, max_length: int, newline: bool = False) -> list[str]:
        texts = []
        while len(text) > max_length:
            if newline:
                try:
                    ind = text[:max_length].rindex("\n")
                except ValueError:
                    # No newline was found so fall back to character count
                    ind = max_length
            else:
                ind = max_length

            texts.append(text[:ind])
            # The +1 is to remove the newline character
            text = text[ind + 1:]
        texts.append(text)
        return texts

    async def on_application_command_error(self, ctx: ApplicationContext, exception: DiscordException) -> None:
        if (w := self.config["error_logging_webhook"]) is not None:
            text = f"Error In {ctx.command.qualified_name} Guild ID: {ctx.guild_id} Channel ID: {ctx.channel_id}\n"
            text += "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            for i in self._split_text(text, 1990, newline=True):
                await w.send(f"```py\n{i}\n```")
        await ctx.respond(embed=await ef.error("An Error Occurred"))
        raise exception

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        if (w := self.config["error_logging_webhook"]) is not None:
            text = "Error In " + event_method + "\n"
            text += traceback.format_exc()
            for i in self._split_text(text, 1990, newline=True):
                await w.send(f"```py\n{i}\n```")
        traceback.print_exc()
