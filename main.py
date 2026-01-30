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

import asyncio
import logging

import twitchio

from database import Database
from time2grow import CONFIG, Bot


LOGGER: logging.Logger = logging.getLogger(__name__)


def main() -> None:
    twitchio.utils.setup_logging(level=CONFIG["general"]["logging"])

    DB_CONFIG = CONFIG["database"]
    BOT_CONFIG = CONFIG["bot"]

    password = DB_CONFIG["password"]
    dsn = DB_CONFIG["dsn"]
    enc_key = DB_CONFIG["encryption_key"]

    async def runner() -> None:
        async with Database(password=password, dsn=dsn, encryption_key=enc_key) as db, Bot(db, **BOT_CONFIG) as bot:
            await bot.start(save_tokens=False)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down due to KeyboardInterrupt.")


if __name__ == "__main__":
    main()
