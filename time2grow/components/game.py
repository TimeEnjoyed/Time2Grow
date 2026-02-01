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
import threading
import time
from collections import deque
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import twitchio
from twitchio import Colour
from twitchio.ext import commands

from ..config import CONFIG
from ..exceptions import *
from ..plants import Plant


if TYPE_CHECKING:
    from ..bot import Bot
    from ..types_ import RewardCommandCoro, RewardCommandMappingT


LOGGER: logging.Logger = logging.getLogger(__name__)
type CBCoro = Callable[[GameLoop, set[Plant]], Coroutine[Any, Any, None]]


class GameLoop(threading.Thread):
    TICK: float = 1.0

    def __init__(self, loop: asyncio.AbstractEventLoop, *, cb: CBCoro, max_plants: int) -> None:
        self._plants: dict[str, Plant] = {}
        self._plant_queue: deque[Plant] = deque()
        self._max_plants = max_plants

        self.loop = loop
        self.cb = cb

        self.lock: threading.Lock = threading.Lock()
        self.populating_event: threading.Event = threading.Event()
        self.populating_event.set()

        self._should_close: bool = False
        super().__init__(daemon=True)

    def run(self) -> None:
        while not self._should_close:
            time.sleep(self.TICK)

            if self._plant_queue:
                self._populate()

            updates: set[Plant] = set()
            for uid, plant in self._plants.copy().items():
                if plant.should_exit():
                    updates.add(plant)

                    with self.lock:
                        self._plants.pop(uid, None)

                    continue

                if plant.should_update():
                    plant.update()

                if plant.has_updates:
                    updates.add(plant)

            if self._should_close:
                break

            if updates:
                self.update(updates)

    def update(self, updates: set[Plant]) -> None:
        self.loop.call_soon_threadsafe(self.cb, self, updates)

    def add_plant(self, plant: Plant) -> None:
        if len(self._plants) + len(self._plant_queue) >= self._max_plants:
            raise PlantsFullError("Too many plants are currently active in the game.")

        if plant.uid in self._plants:
            raise PlantExistsError("User already has a plant on this channel.")

        self.populating_event.wait()
        self._plant_queue.append(plant)

    def _populate(self) -> None:
        self.populating_event.clear()

        while self._plant_queue:
            plant = self._plant_queue.popleft()

            with self.lock:
                self._plants[plant.uid] = plant

        self.populating_event.set()

    def terminate(self) -> None:
        self._should_close = True

    @property
    def closing(self) -> bool:
        return self._should_close


class GameComponent(commands.Component):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        game_config = CONFIG["game"]

        self.grace: int = game_config["grace_period"]
        self.games: dict[twitchio.PartialUser, GameLoop] = {}
        self.end_tasks: dict[twitchio.PartialUser, asyncio.Task[None]] = {}

        plant_cost: int = game_config["plant_cost"]
        attack_cost: int = game_config["attack_cost"]
        water_cost: int = game_config["water_cost"]
        help_cost: int = game_config["help_cost"]
        shield_cost: int = game_config["shield_cost"]

        self.reward_commands: dict[str, RewardCommandMappingT] = {
            "plant": {"cb": self.plant_cb, "colour": Colour.green(), "cost": plant_cost, "prompt": None},
            "attack": {
                "cb": self.attack_cb,
                "colour": Colour.red(),
                "cost": attack_cost,
                "prompt": "Enter a user to attack",
            },
            "water": {"cb": self.water_cb, "colour": Colour.blue(), "cost": water_cost, "prompt": None},
            "help": {"cb": self.help_cb, "colour": Colour.hot_pink(), "cost": help_cost, "prompt": "Enter a user to help"},
            "shield": {"cb": self.shield_cb, "colour": Colour.cadet_blue(), "cost": shield_cost, "prompt": None},
        }

    async def component_load(self) -> None:
        self.loop = asyncio.get_event_loop()

    async def component_teardown(self) -> None:
        for game in self.games.values():
            game.terminate()

    async def loop_callback(self, game: GameLoop, plants: set[Plant]) -> None:
        if game.closing:
            return

        for plant in plants:
            await plant.update_meta()

        # Dispatch to JS...

    async def end_game(self, broadcaster: twitchio.PartialUser) -> None:
        delay = self.grace * 60

        LOGGER.debug("Waiting %d seconds before terminating game loop thread for '%s'.", delay, broadcaster.name)
        await asyncio.sleep(delay)

        game = self.games.pop(broadcaster, None)
        if game:
            game.terminate()

        LOGGER.info("Successfully terminated game loop thread for '%s'.", broadcaster.name)

    async def setup_game(self, broadcaster: twitchio.PartialUser) -> None:
        LOGGER.info("Attemping to start the game loop thread and add commands for '%s'.", broadcaster.name)

        game = GameLoop(self.loop, cb=self.loop_callback, max_plants=CONFIG["game"]["max_plants"])
        self.games[broadcaster] = game

        # Fetch broadcaster rewards and create reward commands...
        # Create any missing rewards...

        rewards = await broadcaster.fetch_custom_rewards(manageable=True)
        commands_copy = set(self.reward_commands.keys())

        for reward in rewards:
            if reward.title not in commands_copy:
                continue

            commands_copy.discard(reward.title)
            self.create_reward_command(reward.title, reward.id)

        for name in commands_copy:
            # They don't have this manageable reward: Create it and add the command...
            rid = await self.create_reward(broadcaster=broadcaster, name=name)
            self.create_reward_command(name, rid)

        game.start()
        LOGGER.info("Successfully started the game for '%s'.", broadcaster.name)

    async def create_reward(self, *, broadcaster: twitchio.PartialUser, name: str) -> str:
        """Creates a Custom Reward on the Broadcasters Channel.

        Will be one of the defined Game Rewards used to play.
        """
        LOGGER.info("Generating missing custom reward '%s' for '%s'.", name, broadcaster.name)

        data = self.reward_commands[name]
        cost = data["cost"]
        prompt = data["prompt"]
        colour = data["colour"]

        reward = await broadcaster.create_custom_reward(
            title=name,
            cost=cost,
            redemptions_skip_queue=False,
            prompt=prompt,
            background_color=colour,
        )
        return reward.id

    def create_reward_command(self, name: str, id: str) -> None:
        """Creates a commands.RewardCommand from the Broadcasters Custom Rewards and adds it to the Bot."""
        cb: RewardCommandCoro = self.reward_commands[name]["cb"]
        command: commands.RewardCommand[commands.Component, ...] = commands.RewardCommand(
            cb,
            reward_id=id,
            invoke_when=commands.RewardStatus.unfulfilled,
        )

        try:
            self.bot.add_command(command)
        except commands.CommandExistsError:
            LOGGER.debug("Command for reward '%s' has already been added.", id)

    async def start_game(self, broadcaster: twitchio.PartialUser) -> None:
        """Attempt to start the game loop for the specified Broadcaster.

        If a current game is ending (E.g. the streamer disconnected briefly) the termination of the game will be interrupted
        and the current game will continue.
        """
        LOGGER.info("Starting game for %s", broadcaster.name)
        task = self.end_tasks.get(broadcaster)

        if not task:
            await self.setup_game(broadcaster)
            return

        try:
            task.cancel()
        except Exception as e:
            LOGGER.debug("An error occurred during cancelation of Game cleanup task: %s.", e)

    @commands.Component.listener()
    async def event_stream_online(self, payload: twitchio.StreamOnline) -> None:
        """Attempt to start the game loop when the Broadcaster goes live.

        There is a grace period of X minutes (Default: 10).
        """
        await self.start_game(payload.broadcaster)

    @commands.Component.listener()
    async def event_stream_offline(self, payload: twitchio.StreamOffline) -> None:
        """Attempt to end the game loop when the Broadcaster ends stream.

        There is a grace period of X minutes (Default: 10).
        """
        # Give stream a grace period of X minutes...
        task = asyncio.create_task(self.end_game(payload.broadcaster))
        self.end_tasks[payload.broadcaster] = task

    async def add_plant(self, game: GameLoop, plant: Plant) -> None:
        """Add a plant to the game.

        This method calls the game loop add_plant method in to_thread as the loop has a synchronization lock when populating
        or modifying plants.
        """
        async with asyncio.timeout(5):
            await asyncio.to_thread(game.add_plant, plant)

    async def plant_cb(self, ctx: commands.Context[Bot], *, inp: str | None = None) -> None:
        """Reward Command for 'plant' which creates a new plant for the specified user on the current channel."""
        broadcaster = ctx.broadcaster
        game = self.games.get(broadcaster)

        # NOTE: All unfulfilled; ContexType is always REWARD.
        assert ctx.type is commands.ContextType.REWARD and isinstance(ctx.redemption, twitchio.ChannelPointsRedemptionAdd)

        if not game:
            await ctx.send(f"{ctx.chatter.mention} the plant game cannot be used here currently.")
            await ctx.redemption.refund(token_for=broadcaster)
            return

        plant = Plant(user=ctx.chatter)

        try:
            await self.add_plant(game, plant)
            await ctx.send(f"{ctx.chatter.mention} added a plant to the garden!")
            await ctx.redemption.fulfill(token_for=broadcaster)
            return
        except PlantsFullError:
            await ctx.send(f"{ctx.chatter.mention} the garden is full. Try again when a plant wittles away.")
        except PlantExistsError:
            await ctx.send(f"{ctx.chatter.mention} you already own a plant.")
        except TimeoutError:
            LOGGER.debug("TimeoutError occurred adding plant to game loop for broadcaster: '%s'.", broadcaster.name)
            await ctx.send(f"{ctx.chatter.mention} an error occurred adding your plant. Please try again later.")

        await ctx.redemption.refund(token_for=broadcaster)

    async def attack_cb(self, ctx: commands.Context[Bot], *, inp: str) -> None: ...

    async def water_cb(self, ctx: commands.Context[Bot], *, inp: str | None = None) -> None: ...

    async def help_cb(self, ctx: commands.Context[Bot], *, inp: str) -> None: ...

    async def shield_cb(self, ctx: commands.Context[Bot], *, inp: str | None = None) -> None: ...


async def setup(bot: Bot) -> None:
    await bot.add_component(GameComponent(bot))
