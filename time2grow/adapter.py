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
import json
from collections import defaultdict
from typing import TYPE_CHECKING, cast

from sse_starlette import EventSourceResponse
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from twitchio import web


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

    from .bot import Bot
    from .components.game import GameComponent, GameLoop
    from .plants import Plant
    from .types_ import DispatchDataT


class GameAdapter(web.StarletteAdapter["Bot"]):
    def __init__(self, *, host: str, port: int, client: Bot, domain: str | None = None) -> None:
        super().__init__(host=host, port=port, client=client, domain=domain)
        self.queues: dict[str, set[asyncio.Queue[DispatchDataT]]] = defaultdict(set)

        self.add_route("/overlays/{identifier}", self.game_overlay, methods=["GET"])
        self.add_route("/overlays/{identifier}/sse", self.sse_endpoint, methods=["GET"])
        self.mount("/static", app=StaticFiles(directory="static", html=False), name="static")

    async def dispatch(self, game: GameLoop, *, plants: set[Plant]) -> None:
        queues = self.queues[game.overlay_id]
        data: DispatchDataT = {"plants": [p.to_send() for p in plants], "fresh": False, "positions": game.sort_positions()}

        for queue in queues:
            await queue.put(data)

    async def sse_source(
        self,
        request: Request,
        *,
        queue: asyncio.Queue[DispatchDataT],
        broadcaster: str,
    ) -> AsyncGenerator[str]:
        # TODO: Better error...
        component: GameComponent = cast("GameComponent", self.client.get_component("GameComponent"))
        if not component:
            raise RuntimeError

        user = self.client.create_partialuser(user_id=broadcaster)
        game = component.games.get(user)

        if game:
            data: DispatchDataT = {
                "plants": [p.copy().to_send() for p in game._plants.values()],
                "fresh": True,
                "positions": game.sort_positions(),
            }
            yield json.dumps(data)

        while True:
            try:
                data: DispatchDataT = await queue.get()
                yield json.dumps(data)
            except asyncio.CancelledError:
                break

            if await request.is_disconnected():
                break

        identifier: str = request.path_params["identifier"]
        self.queues[identifier].discard(queue)

    async def sse_endpoint(self, request: Request) -> EventSourceResponse | Response:
        identifier: str = request.path_params["identifier"]

        model = await self.client.db.fetch_broadcaster_by_overlay(identifier)
        if not model:
            return Response(status_code=404)

        self.client.overlays[model.uid] = identifier

        queue: asyncio.Queue[DispatchDataT] = asyncio.Queue()
        self.queues[identifier].add(queue)

        return EventSourceResponse(self.sse_source(request, queue=queue, broadcaster=model.uid))

    async def game_overlay(self, request: Request) -> Response:
        identifier: str = request.path_params["identifier"]

        model = await self.client.db.fetch_broadcaster_by_overlay(identifier)
        if not model:
            return Response(content="The provided overlay key is not valid", status_code=404)

        return FileResponse("static/index.html", media_type="text/html", content_disposition_type="inline")
