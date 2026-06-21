"""Flickies runtime config — env-var parsed, fail-fast validated."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    device: str
    engines_file: Path
    data_dir: Path
    enabled_engines: frozenset[str]
    enable_noncommercial: bool
    engines: dict[str, dict] = field(default_factory=dict)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_bool(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in _TRUTHY


def load() -> Config:
    engines_file = Path(_env("FLICKIES_ENGINES_FILE", "/app/engines.json"))
    if not engines_file.is_file():
        raise FileNotFoundError(f"engines file not found: {engines_file}")
    engines = json.loads(engines_file.read_text()).get("engines", {})

    enabled_raw = _env("FLICKIES_ENABLED_ENGINES", "").strip()
    enabled = frozenset(s for s in (e.strip() for e in enabled_raw.split(",")) if s)

    data_dir = Path(_env("FLICKIES_DATA_DIR", "/data"))

    port_raw = _env("FLICKIES_PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError as e:
        raise ValueError(f"FLICKIES_PORT not an int: {port_raw!r}") from e
    if not (1 <= port <= 65535):
        raise ValueError(f"FLICKIES_PORT out of range: {port}")

    return Config(
        host=_env("FLICKIES_HOST", "127.0.0.1"),
        port=port,
        device=_env("FLICKIES_DEVICE", "auto"),
        engines_file=engines_file,
        data_dir=data_dir,
        enabled_engines=enabled,
        enable_noncommercial=_env_bool("FLICKIES_ENABLE_NONCOMMERCIAL"),
        engines=engines,
    )
