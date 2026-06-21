"""Engine registry — lazy load, hot-swap eviction, idle unload.

One GPU pool, one resident engine at a time. Audiolla/talkies pattern:

  - Lazy load on first request for engine X.
  - If a request arrives for engine Y != X, evict X (free VRAM), then load Y.
    This is "hot-swap eviction" — different model name displaces the current.
  - A background sweeper unloads any engine that has been idle longer than
    FLICKIES_IDLE_UNLOAD_SECS (default 600 = 10 minutes).
  - ffmpeg / ffprobe are NOT engines — they're plain singletons attached
    to `app.state.ffmpeg`. The registry only manages the ML pool.

The registry is process-global. FastAPI handlers call
``await registry.acquire(slug)`` → get the warm Engine instance → call its
capability method. The lock around acquire serialises hot-swaps so two
concurrent requests for different models can't race.
"""
from __future__ import annotations

import asyncio
import os
import logging
from typing import Iterable

from flickies.engines.base import Engine


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
        return self._loaded_slug

    # ── acquire (hot-swap eviction) ────────────────────────────────────
    async def acquire(self, slug: str) -> Engine:
        """Return the requested Engine, loaded and ready.

        If a different slug is currently resident, evict it first.
        """
        eng = self.get(slug)
        async with self._swap_lock:
            current = self._loaded_slug
            if current is not None and current != slug:
                old = self._engines.get(current)
                if old is not None and old.loaded():
                    log.info(
                        "hot-swap eviction",
                        extra={
                            "engine_slug": current,
                            "requested": slug,
                            "reason": "different_engine_requested",
                        },
                    )
                    await old.unload()
                self._loaded_slug = None
            await eng.get_model()
            if eng.loaded():
                self._loaded_slug = slug
        return eng

    # ── sweeper ────────────────────────────────────────────────────────
    async def _sweep_once(self) -> None:
        threshold = _idle_unload_secs()
        for slug, eng in list(self._engines.items()):
            if not eng.loaded():
                continue
            idle = eng.last_used_secs_ago()
            if idle is None:
                continue
            if idle >= threshold:
                log.info(
                    "idle eviction",
                    extra={
                        "engine_slug": slug,
                        "idle_secs": idle,
                        "threshold_secs": threshold,
                        "reason": "idle_timeout",
                    },
                )
                await eng.unload()
                if self._loaded_slug == slug:
                    self._loaded_slug = None

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
        try:
            await self._sweeper_task
        except asyncio.CancelledError:
            pass
        self._sweeper_task = None
