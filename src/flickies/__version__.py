"""Canonical version derivation.

Single source of truth = pyproject.toml `[project] version`. Hatchling
writes it into dist-info at build time; importlib.metadata reads it
here. NEVER hardcode the version string in this file.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version


try:
    __version__ = _pkg_version("flickies")
except PackageNotFoundError:
    # Source checkout, package not installed via `uv sync` / `pip install`.
    # Sentinel makes the bug obvious; never fall back to a hardcoded number.
    __version__ = "0.0.0+source"
