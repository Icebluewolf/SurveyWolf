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


class SurveyWolf(discord.Bot):
    # def __init__(self, description=None, *args, **options):
    #     super().__init__(self, *args, **options)

    async def get_application_context(self, interaction: Interaction, cls=None) -> discord.ApplicationContext:
        return await super().get_application_context(interaction, cls=cls or AdvContext)

    # THIS IS FROM ME TESTING RELOADING COGS IT WILL BREAK BOT IF UN-COMMENTED
    # from typing import Literal
    # async def sync_commands(
    #     self,
    #     commands: list | None = None,
    #     method: Literal["individual", "bulk", "auto"] = "bulk",
    #     force: bool = False,
    #     guild_ids: list[int] | None = None,
    #     register_guild_commands: bool = True,
    #     check_guilds: list[int] | None = [],
    #     delete_existing: bool = True,
    # ) -> None:
    #     check_guilds = list(set((check_guilds or []) + (self._bot.debug_guilds or [])))
    #
    #     command_list = []
    #     if commands is None:
    #         commands = self.pending_application_commands
    #         # command_list = self.pending_application_commands.copy()
    #         # self._pending_application_commands = []
    #         # for i in range(len(self.pending_application_commands)):
    #         #     self.pending_application_commands.pop(0)
    #
    #     if guild_ids is not None:
    #         for cmd in commands:
    #             cmd.guild_ids = guild_ids
    #
    #     global_commands = [cmd for cmd in commands if cmd.guild_ids is None]
    #     registered_commands = await self.register_commands(
    #         global_commands, method=method, force=force, delete_existing=delete_existing
    #     )
    #
    #     registered_guild_commands: dict[int, list] = {}
    #
    #     if register_guild_commands:
    #         cmd_guild_ids: list[int] = []
    #         for cmd in commands:
    #             if cmd.guild_ids is not None:
    #                 cmd_guild_ids.extend(cmd.guild_ids)
    #         if check_guilds is not None:
    #             cmd_guild_ids.extend(check_guilds)
    #         for guild_id in set(cmd_guild_ids):
    #             guild_commands = [
    #                 cmd
    #                 for cmd in commands
    #                 if cmd.guild_ids is not None and guild_id in cmd.guild_ids
    #             ]
    #             app_cmds = await self.register_commands(
    #                 guild_commands,
    #                 guild_id=guild_id,
    #                 method=method,
    #                 force=force,
    #                 delete_existing=delete_existing,
    #             )
    #             registered_guild_commands[guild_id] = app_cmds
    #             print("Sync Commands App Commands: ", len(app_cmds))
    #
    #     for i in registered_commands:
    #         cmd = discord.utils.get(
    #             self.pending_application_commands,
    #             name=i["name"],
    #             guild_ids=None,
    #             type=i.get("type"),
    #         )
    #         if cmd:
    #             cmd.id = i["id"]
    #             self._application_commands[cmd.id] = cmd
    #             command_list.append(cmd)  # MY line
    #
    #     if register_guild_commands and registered_guild_commands:
    #         for guild_id, guild_cmds in registered_guild_commands.items():
    #             for i in guild_cmds:
    #                 cmd = discord.utils.find(
    #                     lambda cmd: cmd.name == i["name"]
    #                                 and cmd.type == i.get("type")
    #                                 and cmd.guild_ids is not None
    #                                 # TODO: fix this type error (guild_id is not defined in ApplicationCommand Typed Dict)
    #                                 and int(i["guild_id"]) in cmd.guild_ids,  # type: ignore
    #                     self.pending_application_commands,
    #                 )
    #                 if not cmd:
    #                     # command has not been added yet
    #                     continue
    #                 cmd.id = i["id"]
    #                 self._application_commands[cmd.id] = cmd
    #                 command_list.append(cmd)  # MY line
    #     self._pending_application_commands = [v for v in self._pending_application_commands if v not in command_list]
    #     # self._pending_application_commands = command_list
    #     print("Sync commands Count: ", len(self._pending_application_commands))
