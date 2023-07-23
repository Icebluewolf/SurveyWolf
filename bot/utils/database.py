from os import environ
import asyncpg

from asyncpg.exceptions import InterfaceError


class Database:
    def __init__(self) -> None:
        self._connection_pool = None

    async def connect(self):
        if not self._connection_pool:
            self._connection_pool = await asyncpg.create_pool(
                database=environ["db_name"],
                host=environ["db_host"],
                user=environ["db_user"],
                password=environ["db_password"],
                min_size=3,
                max_size=15,
            )

    async def _acquire(self):
        if not self._connection_pool:
            await self.connect()
        conn = await self._connection_pool.acquire()
        return conn

    async def _recycle(self, conn):
        try:
            await self._connection_pool.release(conn)
        except InterfaceError:
            pass

    async def execute(self, sql: str, *args) -> None:
        conn = await self._acquire()
        await conn.execute(sql, *args)
        await self._recycle(conn)

    async def fetchval(self, sql: str, *args, column=0, timeout=None):
        conn = await self._acquire()
        val = await conn.fetchval(sql, *args, column=column, timeout=timeout)
        await self._recycle(conn)
        return val

    async def fetch(self, sql: str, *args) -> list[asyncpg.Record]:
        conn = await self._acquire()
        rows: list[asyncpg.Record] = await conn.fetch(sql, *args)
        await self._recycle(conn)
        return rows or []


database = Database()
