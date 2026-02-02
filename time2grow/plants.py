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

import datetime
import html
import secrets
from typing import TYPE_CHECKING

from .config import CONFIG
from .exceptions import *


if TYPE_CHECKING:
    from twitchio import PartialUser

    from ..database import Database
    from .types_ import PlantJSONT


class Plant:
    MAX_LEVEL: int = 4
    MAX_FLARE: int = 4

    def __init__(self, user: PartialUser, *, db: Database) -> None:
        self.db = db

        self._created = datetime.datetime.now()
        self._has_updates: bool = True  # New plants should send an update...
        self._id = secrets.token_hex(16)

        game_config = CONFIG["game"]
        self._health: int = game_config["base_health"]
        self._wilted: bool = False
        self._level: int = 0
        self._user = user
        self._died_at: datetime.datetime | None = None
        self._updates: int = 0

    def __repr__(self) -> str:
        return f"Plant(owner={self._user}, id={self._id}, level={self._level}, created={self._created})"

    @property
    def id(self) -> str:
        return self._id

    @property
    def created_at(self) -> datetime.datetime:
        return self._created

    @property
    def uid(self) -> str:
        return self._user.id

    @property
    def level(self) -> int:
        return self._level

    @property
    def wilted(self) -> bool:
        return self._wilted

    def flare_level(self) -> int:
        return min(self._level - (self.MAX_LEVEL + 1), self.MAX_FLARE)

    @property
    def has_updates(self) -> bool:
        return self._has_updates

    @has_updates.setter
    def has_updates(self, value: bool) -> None:
        self._has_updates = value

    def should_exit(self) -> bool:
        if not self._died_at:
            return False

        now = datetime.datetime.now()
        return now >= self._died_at + datetime.timedelta(minutes=1)

    def is_new(self) -> bool:
        return self._updates <= 1

    def revive(self) -> None:
        if self.should_exit():
            raise NoReviveError

        self._died_at = None
        self._level = max(self._level - 2, 0)

    def update(self) -> ...:
        self._updates += 1

    async def update_meta(self) -> ...: ...

    def get_base(self) -> str:
        if self.wilted:
            return '<img class="plantImg" src="/static/images/plants/wilted.png>"'

        level = min(self._level, self.MAX_LEVEL)
        return f'<img class="plantImg" src="/static/images/plants/{level}.png"'

    def get_flare(self) -> str:
        flare_level = self.flare_level()

        if flare_level < 0:
            return ""

        return f'<img class="plantFlare" src="/static/images/shields/{flare_level}.png">'

    def generate_html(self) -> str:
        username = html.escape(str(self._user.display_name or self._user.name))

        base = self.get_base()
        banner = '<img class="plantBanner" src="/static/images/banner.png">'
        medal = ""
        user = f'<span class="username">{username}</span>'
        flare = self.get_flare()

        return f"{base}\n{banner}\n{medal}\n{user}\n{flare}\n"

        # //             <div class="plantContainer">
        # //                 <img class="plantImg" src=${plantImg}>
        # //                 <img class="plantBanner" src="images/banner.png">
        # //                 ${medalImg}
        # //                 <span class="username">${username}</span>
        # //                 ${flareImg}
        # //                 ${epicImg}
        # //                 ${waterImg}
        # //                 ${rainImg}
        # //                 ${glassesImg}
        # //                 ${speechImg}
        # //             </div>

    def to_send(self) -> PlantJSONT:
        return {
            "id": self._id,
            "html": self.generate_html(),
            "level": self._level,
            "is_new": self.is_new(),
            "is_dead": self.should_exit(),
        }

    def copy(self) -> Plant:
        obj = Plant(self._user, db=self.db)
        obj._created = self._created
        obj._has_updates = self._has_updates
        obj._id = self._id
        obj._health = self._health
        obj._wilted = self._wilted
        obj._level = self._level
        obj._died_at = self._died_at
        obj._updates = self._updates

        return obj
