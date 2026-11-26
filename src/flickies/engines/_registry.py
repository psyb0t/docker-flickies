"""Engine registry — lazy load, hot-swap eviction, idle unload.

One GPU pool, one resident engine at a time. Audiolla/talkies pattern:

  - Lazy load on first request for engine X.
  - If a request arrives for engine Y != X, evict X (free VRAM), then load Y.
    This is "hot-swap eviction" — different model name displaces the current.
  - A background sweeper unloads any engine that has been idle longer than
    FLICKIES_IDLE_UNLOAD_SECS (default 600 = 10 minutes).
  - ffmpeg / ffprobe are NOT engines — they're plain singletons attached
    to `app.state.ffmpeg`. The registry only manages the ML pool.

The registry holds its lock through inference and model eviction.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Iterable
from typing import Any

from flickies.engines.base import Engine
from flickies.errors import EngineBusy

log = logging.getLogger(__name__)


def _idle_unload_secs() -> float:
    raw = os.environ.get("FLICKIES_IDLE_UNLOAD_SECS", "600").strip()
    try:
        return float(raw)
    except ValueError:
        return 600.0


def _sweep_interval_secs() -> float:
    raw = os.environ.get("FLICKIES_SWEEP_INTERVAL_SECS", "30").strip()
    try:
        return float(raw)
    except ValueError:
        return 30.0


class EngineNotRegistered(KeyError):
    pass


class Registry:
    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}
        self._loaded_slug: str | None = None
        self._active = 0
        self._swap_lock = asyncio.Lock()
        self._sweeper_task: asyncio.Task[None] | None = None

    # ── registration ────────────────────────────────────────────────────
    def register(self, engine: Engine) -> None:
        if engine.slug in self._engines:
            raise ValueError(f"engine already registered: {engine.slug}")
        self._engines[engine.slug] = engine
        log.info("engine registered", extra={"engine_slug": engine.slug})

    def get(self, slug: str) -> Engine:
        try:
            return self._engines[slug]
        except KeyError as e:
            raise EngineNotRegistered(slug) from e

    def slugs(self) -> Iterable[str]:
        return tuple(self._engines.keys())

    def loaded_slug(self) -> str | None:
        slug = self._loaded_slug
        return slug if slug is not None and self.get(slug).loaded() else None

    async def run(self, slug: str, operation: str, *args: Any) -> None:
        engine = self.get(slug)
        self._active += 1
        try:
            async with self._swap_lock:
                current = self._loaded_slug
                if current is not None and current != slug:
                    await self.get(current).unload()
                self._loaded_slug = slug
                await engine.run(operation, *args)
        finally:
            self._active -= 1

    async def unload(self, slug: str | None = None) -> list[str]:
        engines = [self.get(slug)] if slug is not None else list(self._engines.values())
        if self._active or self._swap_lock.locked():
            raise EngineBusy("a video engine is busy")
        async with self._swap_lock:
            unloaded = [engine.slug for engine in engines if engine.loaded()]
            for engine in engines:
                await engine.unload()
                if self._loaded_slug == engine.slug:
                    self._loaded_slug = None
        return unloaded

    async def close(self) -> None:
        async with self._swap_lock:
            for engine in self._engines.values():
                await engine.unload()

    async def _sweep_once(self) -> None:
        threshold = _idle_unload_secs()
        slug = self._loaded_slug
        if self._active or self._swap_lock.locked() or slug is None:
            return
        idle = self.get(slug).last_used_secs_ago()
        if idle is not None and idle >= threshold:
            await self.unload(slug)

    async def _sweep_loop(self) -> None:
        interval = _sweep_interval_secs()
        while True:
            try:
                await asyncio.sleep(interval)
                await self._sweep_once()
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                log.exception("sweeper iteration failed; continuing")

    def start_sweeper(self) -> None:
        if self._sweeper_task is not None and not self._sweeper_task.done():
            return
        self._sweeper_task = asyncio.create_task(self._sweep_loop())
        log.info(
            "sweeper started",
            extra={
                "interval_secs": _sweep_interval_secs(),
                "threshold_secs": _idle_unload_secs(),
            },
        )

    async def stop_sweeper(self) -> None:
        if self._sweeper_task is None:
            return
        self._sweeper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._sweeper_task
        self._sweeper_task = None
