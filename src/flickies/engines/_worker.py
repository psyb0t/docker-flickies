from __future__ import annotations

from typing import Any

from flickies.engines.base import Engine
from flickies.model_process import ModelProcess


class EngineWorker:
    def __init__(self, factory: type[Engine], slug: str, spec: dict[str, Any]) -> None:
        self.engine: Any = factory(slug=slug, **spec)

    async def execute(self, operation: str, *args: Any) -> Any:
        if operation == "lipsync":
            return await self.engine.lipsync(*args)
        if operation == "restore":
            return await self.engine.restore(*args)
        raise ValueError("unknown video operation")

    def resident(self) -> bool:
        return bool(self.engine.loaded())

    async def close(self) -> None:
        # The whole process is exiting, including its CUDA context.
        return None


class WorkerEngine(Engine):
    def __init__(self, factory: type[Engine], slug: str, **spec: Any) -> None:
        super().__init__(slug, **spec)
        self.process = ModelProcess(EngineWorker, factory, slug, spec)

    def loaded(self) -> bool:
        return bool(self.process.resident)

    async def run(self, operation: str, *args: Any) -> Any:
        try:
            return await self.process.call(operation, *args)
        finally:
            self._touch()

    async def unload(self) -> None:
        await self.process.stop()

    async def health(self) -> dict[str, Any]:
        return {"loaded": self.loaded()}
