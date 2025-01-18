import asyncio
from asyncio import sleep
from datetime import datetime, timedelta
from time_str import IntervalConverter
from collections.abc import Callable


class Timer:
    def __init__(self, time: timedelta | datetime | str, callback: Callable, *args, **kwargs):
        """
        Creates a timer that starts now and ends after the duration. Calls the function with args and kwargs on
        completion.
        :param time: When a string is given it will be parsed into a timedelta. An end time can also be given.
        :param callback: The function to call on completion.
        :param args: The arguments to pass to the callback function.
        :param kwargs: The keyword arguments to pass to the callback function.
        """
        self.start_time = datetime.now()
        if isinstance(time, str):
            duration = self.str_time(time)
        elif isinstance(time, timedelta):
            duration = time
        elif isinstance(time, datetime):
            duration = time - self.start_time
        else:
            raise ValueError("Time Must Be A str, timedelta, Or datetime Object")

        self.end_time: datetime = self.start_time + duration
        self.duration = duration
        self.callback = (callback, args, kwargs)

        # Start Timer
        if self.duration.total_seconds() > 0:
            self._task = asyncio.create_task(self._job())

    @staticmethod
    def str_time(time: str) -> timedelta:
        converter = IntervalConverter(time, max_unit="days")
        return converter.timedelta_relative()

    async def _job(self):
        await sleep(self.duration.total_seconds())
        await self.callback[0](*self.callback[1], **self.callback[2])

    async def cancel(self):
        if self._task:
            self._task.cancel()
