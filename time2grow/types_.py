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

from typing import TYPE_CHECKING, Protocol, TypedDict


if TYPE_CHECKING:
    from twitchio.ext import commands
    from twitchio.utils import Colour

    from .bot import Bot


class RewardCommandCoro(Protocol):
    async def __call__(self, ctx: commands.Context[Bot], *, inp: str) -> None: ...


class BotOptionsT(TypedDict):
    client_id: str
    client_secret: str
    bot_id: str
    owner_id: str
    prefix: list[str]


class GeneralConfigT(TypedDict):
    logging: int


class DatabaseConfigT(TypedDict):
    password: str
    dsn: str
    encryption_key: str


class GameConfigT(TypedDict):
    max_plants: int
    base_health: int
    grace_period: int
    plant_cost: int
    attack_cost: int
    water_cost: int
    help_cost: int
    shield_cost: int


class ConfigT(TypedDict):
    general: GeneralConfigT
    database: DatabaseConfigT
    bot: BotOptionsT
    game: GameConfigT


class RewardCommandMappingT(TypedDict):
    cb: RewardCommandCoro
    prompt: str | None
    cost: int
    colour: Colour
