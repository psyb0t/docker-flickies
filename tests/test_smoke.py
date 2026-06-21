"""Smoke tests — config loads, engines.json + openapi.yaml parse, registry
basics work, non-commercial gate refuses when not opted in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_engines_json_parses() -> None:
    data = json.loads((REPO_ROOT / "engines.json").read_text())
    engines = data["engines"]
    expected = {"wav2lip", "wav2lip-gan", "latentsync-1.5", "gfpgan"}
    assert expected.issubset(set(engines.keys()))
    for slug, spec in engines.items():
        assert "executor" in spec, f"{slug} missing executor"
        assert "description" in spec, f"{slug} missing description"
    # Non-commercial gate applies to wav2lip variants.
    assert engines["wav2lip"].get("noncommercial") is True
    assert engines["wav2lip-gan"].get("noncommercial") is True
    assert engines["latentsync-1.5"].get("noncommercial", False) is False


def test_openapi_yaml_exists_and_has_paths() -> None:
    p = REPO_ROOT / "openapi.yaml"
    assert p.is_file(), "openapi.yaml missing — see scripts/generate_models.sh"
    body = p.read_text()
    for marker in (
        "openapi:",
        "/v1/health",
        "/v1/video/lipsync",
        "/v1/video/restore",
        "/v1/video/info",
        "VideoLipsyncRequest",
        "ErrorBody",
    ):
        assert marker in body, f"openapi.yaml missing marker: {marker}"


def test_version_derives_from_pyproject() -> None:
    """Versioning rule: pyproject.toml is the canonical source;
    runtime `__version__` derives via importlib.metadata. Never hardcoded.
    Verify the derivation works AND matches pyproject."""
    import re
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert m is not None, "pyproject.toml missing [project] version"
    canonical = m.group(1)

    from flickies import __version__
    # Either the installed package matches pyproject, or we're in a
    # bare source checkout w/ the sentinel — both are valid states; the
    # sentinel is intentionally NOT a hardcoded version number.
    assert __version__ in (canonical, "0.0.0+source"), (
        f"version drift: pyproject={canonical} runtime={__version__}"
    )

    version_file = (REPO_ROOT / "src" / "flickies" / "__version__.py").read_text()
    assert "importlib.metadata" in version_file, (
        "__version__.py must derive via importlib.metadata, not hardcode"
    )


def test_noncommercial_gate_refuses_when_not_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLICKIES_ENABLE_NONCOMMERCIAL", raising=False)
    from flickies.engines._license_gate import (
        NonCommercialOptInRequired,
        noncommercial_enabled,
        require_noncommercial_optin,
    )

    assert noncommercial_enabled() is False
    with pytest.raises(NonCommercialOptInRequired):
        require_noncommercial_optin("wav2lip")


def test_noncommercial_gate_passes_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLICKIES_ENABLE_NONCOMMERCIAL", "1")
    from flickies.engines._license_gate import (
        noncommercial_enabled,
        require_noncommercial_optin,
    )

    assert noncommercial_enabled() is True
    # Should not raise.
    require_noncommercial_optin("wav2lip")


def test_config_loads_with_engines_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    from flickies.config import load

    cfg = load()
    assert cfg.engines, "engines dict empty after load"
    assert "wav2lip" in cfg.engines
    assert cfg.enable_noncommercial in (True, False)


def test_registry_basic_lifecycle() -> None:
    from flickies.engines._registry import Registry
    from flickies.engines.gfpgan import GFPGAN

    r = Registry()
    r.register(GFPGAN(slug="gfpgan"))
    assert "gfpgan" in r.slugs()
    assert r.loaded_slug() is None
    assert r.get("gfpgan").slug == "gfpgan"
