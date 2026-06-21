"""Pytest config — ensure src/ is on sys.path when running outside the dev image,
and register the gpu / hf_gated / noncommercial markers used by integration tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_engines_json = _ROOT / "engines.json"
if _engines_json.exists():
    os.environ.setdefault("FLICKIES_ENGINES_FILE", str(_engines_json))


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _is_set(env: str) -> bool:
    return os.environ.get(env, "").strip().lower() in _TRUTHY


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "gpu: requires a CUDA-capable GPU (set HARNESS_GPU=1 to enable).",
    )
    config.addinivalue_line(
        "markers",
        "hf_gated: requires HF_TOKEN / HUGGINGFACE_TOKEN to access gated weights.",
    )
    config.addinivalue_line(
        "markers",
        "noncommercial: requires FLICKIES_ENABLE_NONCOMMERCIAL=1.",
    )
    config.addinivalue_line(
        "markers",
        "engine(*slugs): integration tests declare which engines the container needs.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    _ = config  # pytest hook signature requires config; unused here
    skip_gpu = pytest.mark.skip(reason="HARNESS_GPU not set")
    skip_hf = pytest.mark.skip(reason="HF_TOKEN / HUGGINGFACE_TOKEN not set")
    skip_nc = pytest.mark.skip(reason="FLICKIES_ENABLE_NONCOMMERCIAL not set")

    have_gpu = _is_set("HARNESS_GPU")
    have_hf = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN"))
    have_nc = _is_set("FLICKIES_ENABLE_NONCOMMERCIAL")

    for item in items:
        if "gpu" in item.keywords and not have_gpu:
            item.add_marker(skip_gpu)
        if "hf_gated" in item.keywords and not have_hf:
            item.add_marker(skip_hf)
        if "noncommercial" in item.keywords and not have_nc:
            item.add_marker(skip_nc)
