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

import datetime
import secrets
from typing import TYPE_CHECKING

from .config import CONFIG


if TYPE_CHECKING:
    from twitchio import PartialUser


class Plant:
    def __init__(self, user: PartialUser) -> None:
        self._has_updates: bool = True  # New plants should send an update...
        self._died_at: datetime.datetime | None = None
        self._id = secrets.token_hex(16)
        self._user = user

        game_config = CONFIG["game"]
        self._health: int = game_config["base_health"]

    @property
    def id(self) -> str:
        return self._id

    @property
    def uid(self) -> str:
        return self._user.id

    @property
    def has_updates(self) -> bool:
        return self._has_updates

    @has_updates.setter
    def has_updates(self, value: bool) -> None:
        self.has_updates = value

    def should_update(self) -> bool:
        return self._has_updates

    def should_exit(self) -> bool:
        if not self._died_at:
            return False

        now = datetime.datetime.now()
        return now >= self._died_at + datetime.timedelta(minutes=1)

    def update(self) -> ...: ...

    async def update_meta(self) -> ...:
        self.has_updates = False
