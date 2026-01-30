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

import logging
from typing import TYPE_CHECKING, Unpack, cast

import twitchio
from twitchio import eventsub
from twitchio.ext import commands

from .adapter import GameAdapter


if TYPE_CHECKING:
    from twitchio.authentication import UserTokenPayload, ValidateTokenPayload

    from database import Database

    from .components.game import GameComponent
    from .types_ import BotOptionsT


LOGGER: logging.Logger = logging.getLogger(__name__)


# Required scopes from broadcasters...
SCOPES: twitchio.Scopes = twitchio.Scopes()
SCOPES.channel_manage_redemptions = True
SCOPES.channel_read_redemptions = True
SCOPES.channel_bot = True


class Bot(commands.AutoBot):
    def __init__(self, db: Database, **options: Unpack[BotOptionsT]) -> None:
        self.db = db
        self.overlays: dict[str, str] = {}

        adapter = GameAdapter(host="localhost", port=4343, client=self)
        super().__init__(**options, scopes=SCOPES, adapter=adapter)

    async def setup_hook(self) -> None:
        await self.load_module(".", package="time2grow.components")
        await self.load_overlays()

    async def load_overlays(self) -> None:
        overlays = await self.db.fetch_broadcasters()
        self.overlays = {o.uid: o.overlay_id for o in overlays}

    async def event_ready(self) -> None:
        LOGGER.info("Successfully logged in as %s", self.user)

    async def event_oauth_authorized(self, payload: UserTokenPayload) -> None:
        if not payload.user_id:
            return

        await self.add_token(payload.access_token, payload.refresh_token)

        if payload.user_id == self.user.id:  # type: ignore [Reason: We always pass bot_id]
            return

        await self.subscribe(payload.user_id)

        user = self.create_partialuser(user_id=payload.user_id)
        game_component: GameComponent = cast("GameComponent", self.get_component("GameComponent"))
        await game_component.setup_game(user)

    async def subscribe(self, user_id: str) -> None:
        subs: list[eventsub.SubscriptionPayload] = [
            eventsub.ChannelPointsRedeemAddSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPointsRedeemUpdateSubscription(broadcaster_user_id=user_id),
            eventsub.StreamOnlineSubscription(broadcaster_user_id=user_id),
            eventsub.StreamOfflineSubscription(broadcaster_user_id=user_id),
            eventsub.ChatMessageSubscription(broadcaster_user_id=user_id, user_id=self.bot_id),
        ]

        await self.multi_subscribe(subs)

    async def add_token(self, token: str, refresh: str) -> ValidateTokenPayload:
        validated = await super().add_token(token, refresh)

        if validated.user_id:
            await self.db.add_token(validated.user_id, token=token, refresh=refresh)

        return validated

    async def load_tokens(self, path: str | None = None) -> None:
        tokens = await self.db.fetch_tokens()

        for model in tokens:
            await self.add_token(model.token, model.refresh)

    def add_command(self, command: commands.Command[commands.Component, ...]) -> None:
        return super().add_command(command)
