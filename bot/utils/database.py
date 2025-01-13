import json
from contextlib import asynccontextmanager
from os import environ
import asyncpg

from asyncpg.exceptions import InterfaceError
from asyncpg.transaction import Transaction


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
        conn: asyncpg.Connection = await self._connection_pool.acquire()
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
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

    async def fetch_one(self, sql: str, *args) -> asyncpg.Record | None:
        conn = await self._acquire()
        row: asyncpg.Record = await conn.fetchrow(sql, *args)
        await self._recycle(conn)
        return row

    @asynccontextmanager
    async def transaction(self) -> tuple[asyncpg.Connection, Transaction]:
        conn = None
        try:
            conn = await self._acquire()
            async with conn.transaction():
                yield conn
        finally:
            if conn is not None:
                await self._recycle(conn)


database = Database()
