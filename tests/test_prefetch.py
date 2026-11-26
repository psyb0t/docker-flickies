from __future__ import annotations

from pathlib import Path

import pytest

from flickies import prefetch

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("mode", "slugs", "expected"),
    [
        ("", "", []),
        ("", "gfpgan", ["gfpgan"]),
        ("startup", "gfpgan", ["gfpgan"]),
        ("startup", "", ["gfpgan"]),
        ("on-demand", "gfpgan", []),
    ],
)
def test_startup_model_selection(monkeypatch, tmp_path, mode, slugs, expected):
    monkeypatch.setenv("FLICKIES_MODEL_DOWNLOAD", mode)
    monkeypatch.setenv("FLICKIES_ENABLED_ENGINES", slugs)
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLICKIES_LOG_FILE", str(tmp_path / "test.log"))
    monkeypatch.setenv("FLICKIES_DEVICE", "cpu")
    monkeypatch.delenv("FLICKIES_PREFETCH_ALL", raising=False)
    monkeypatch.delenv("FLICKIES_OFFLINE", raising=False)
    monkeypatch.delenv("FLICKIES_ENABLE_NONCOMMERCIAL", raising=False)
    fetched = []

    def prefetch_one(slug, _spec):
        fetched.append(slug)
        return True

    monkeypatch.setattr(prefetch, "_prefetch_one", prefetch_one)
    assert prefetch.main() == 0
    assert fetched == expected
