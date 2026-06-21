"""Engine protocol — uniform lifecycle.

All engines share lazy-load + idle-unload semantics. ffmpeg / ffprobe are
NOT engines — they're plain singletons (see src/flickies/ffmpeg.py).
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any


class Engine(ABC):
    slug: str

    def __init__(self, slug: str, **spec: Any) -> None:
        self.slug = slug
        self.spec = spec
        self._last_used: float | None = None
        self._lock = asyncio.Lock()

    def loaded(self) -> bool:
        return False

    async def get_model(self) -> Any:
        return None

    async def unload(self) -> None:
        return None

    def last_used_secs_ago(self) -> float | None:
        if self._last_used is None:
            return None
        return time.monotonic() - self._last_used

    def _touch(self) -> None:
        self._last_used = time.monotonic()

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...
