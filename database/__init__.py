"""
MIT License

Copyright (c) 2026 EvieePy <evieepy@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self

import asyncpg
from cryptography.fernet import Fernet

from .models import *


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import twitchio
    from asyncpg.pool import PoolConnectionProxy


LOGGER: logging.Logger = logging.getLogger(__name__)
type PoolT = asyncpg.Pool[asyncpg.Record]


class NoConnectionError(Exception): ...


class Database:
    pool: PoolT

    def __init__(self, *, password: str, dsn: str, max_size: int = 1000, min_size: int = 10, encryption_key: str) -> None:
        self._password = password
        self._dsn = dsn

        self._max_size = max_size
        self._min_size = min_size

        self.fernet = Fernet(encryption_key)

    def __repr__(self) -> str:
        masked = self._dsn.replace(self._password, "REDACTED")
        return f"Database(dsn={masked}, max_size={self._max_size}, min_size={self._min_size})"

    async def __aenter__(self) -> Self:
        return await self.setup()

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.close()

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[PoolConnectionProxy[asyncpg.Record]]:
        connection = await self.pool.acquire()

        try:
            yield connection
        finally:
            await self.pool.release(connection)

    async def setup(self) -> Self:
        LOGGER.info("Setting up Database.")

        try:
            pool: PoolT = await asyncpg.create_pool(dsn=self._dsn, max_size=self._max_size, min_size=self._min_size)
        except Exception as e:
            LOGGER.critical("Unable to open %r connection pool. Terminating.", self)
            raise NoConnectionError from e

        with open("schema.sql") as sql:
            await pool.execute(sql.read())

        LOGGER.info("Sucessfully setup %r.", self)

        self.pool = pool
        return self

    async def close(self) -> None:
        LOGGER.info("Attempting to close %r gracefully.", self)

        # Asyncpg recommends waiting 10s before forceful termination...
        try:
            async with asyncio.timeout(10):
                await self.pool.close()
        except TimeoutError:
            LOGGER.warning("Unable to gracefully close %r Pool: Forcefully terminating.", self)
            self.pool.terminate()
        else:
            LOGGER.info("Sucessfully closed Database.")

    async def fetch_broadcaster_by_overlay(self, oid: str) -> BroadcasterModel | None:
        """Method to fetch a stored broadcaster by overlay ID."""

        query = """SELECT * FROM broadcasters WHERE overlay_id = $1"""

        async with self.acquire() as connection:
            row = await connection.fetchrow(query, oid, record_class=BroadcasterModel)

        return row

    async def fetch_broadcaster(self, uid: str) -> BroadcasterModel | None:
        """Method to fetch a stored broadcaster."""

        query = """SELECT * FROM broadcasters WHERE uid = $1"""

        async with self.acquire() as connection:
            row = await connection.fetchrow(query, uid, record_class=BroadcasterModel)

        return row

    async def fetch_broadcasters(self) -> list[BroadcasterModel]:
        """Method to fetch every stored broadcaster."""

        query = """SELECT * FROM broadcasters"""

        async with self.acquire() as connection:
            rows = await connection.fetch(query, record_class=BroadcasterModel)

        return rows

    async def add_broadcaster(self, user_id: str | twitchio.PartialUser) -> str:
        """Method to add a broadcaster to the database to allow using the game overlay."""

        query = """
        INSERT INTO broadcasters(uid, overlay_id) VALUES($1, $2)
            ON CONFLICT (uid) DO UPDATE SET overlay_id = $2
        """

        overlay_id = secrets.token_hex(24)
        async with self.acquire() as connection:
            await connection.execute(query, str(user_id), overlay_id)

        return overlay_id

    async def add_token(self, user_id: str, *, token: str, refresh: str) -> None:
        """Method to add a user token to the database.

        This method encrypts the access and refresh tokens with the provided fernet key.
        """
        query = """
        INSERT INTO tokens(uid, token, refresh) VALUES($1, $2, $3)
        ON CONFLICT (uid) DO UPDATE SET token = $2, refresh = $3
        """

        encrypted_t = self.fernet.encrypt(token.encode()).decode()
        encrypted_r = self.fernet.encrypt(refresh.encode()).decode()

        async with self.acquire() as connection:
            await connection.execute(query, user_id, encrypted_t, encrypted_r)

    async def fetch_tokens(self) -> list[DecryptedTokenModel]:
        """Method to fetch stored tokens.

        This method returns the decrypted versions of the access and refresh tokens.
        """
        query = """SELECT * FROM tokens"""

        async with self.acquire() as connection:
            rows = await connection.fetch(query, record_class=TokenModel)

        decrypted = [DecryptedTokenModel.from_model(data=m, fernet=self.fernet) for m in rows]
        return decrypted
