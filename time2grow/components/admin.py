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

from typing import TYPE_CHECKING

from twitchio.ext import commands


if TYPE_CHECKING:
    from ..bot import Bot


class AdminComponent(commands.Component):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Component.guard()
    async def is_owner(self, ctx: commands.Context[Bot]) -> bool:
        return ctx.author.id == self.bot.owner_id

    @commands.command()
    async def unload(self, ctx: commands.Context[Bot], *, module: str) -> None:
        await self.bot.unload_module(module)

    @commands.command()
    async def reload(self, ctx: commands.Context[Bot], *, module: str) -> None:
        await self.bot.reload_module(module)


async def setup(bot: Bot) -> None:
    await bot.add_component(AdminComponent(bot))
