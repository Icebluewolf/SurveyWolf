import asyncio
import re
from asyncio import sleep
from datetime import datetime, timedelta
from collections.abc import Callable

# from main import bot
from bot.utils.database import database

# bot.wait_until_ready()


# load all the timers
class Timer:
    def __init__(self, duration: timedelta | str, callback: Callable, *args, **kwargs):
        """
        Creates a timer that starts now and ends after the duration. Calls the function with args and kwargs on
        completion.
        :param duration: When a string is given it will be parsed into a timedelta.
        The string should be in the format ""
        :param callback:
        :param args:
        :param kwargs:
        """

        if isinstance(duration, str):
            duration = self.str_time(duration)

        self.start_time = datetime.now()
        self.end_time: datetime = self.start_time + duration
        self.duration = duration
        self.callback = (callback, args, kwargs)

        # Store timers
        asyncio.create_task(self._store_timer())

        # Start Timer
        self._task = asyncio.create_task(self._job())

    @staticmethod
    def str_time(time: str) -> timedelta:
        letters = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        result = re.findall(r"(\d+?)([a-zA-Z])", time)
        seconds = 0
        for match in result:
            seconds += int(match[0]) * letters[match[1]]
        return timedelta(seconds=seconds)

    async def _store_timer(self):
        sql = """INSERT INTO timers (type, duration, start_time, end_time) VALUES ($1, $2, $3)"""
        await database.execute(sql, self.duration, self.start_time, self.end_time)

    async def _job(self):
        await sleep(self.duration.total_seconds())
        self.callback[0](*self.callback[1], **self.callback[2])

    async def cancel(self):
        self._task.cancel()
