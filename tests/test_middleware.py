"""Middleware tests — request_id echo, rate limit, idempotency."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def base_env(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLICKIES_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FLICKIES_ENABLE_NONCOMMERCIAL", raising=False)
    return tmp_path


def test_request_id_generated_when_missing(base_env, monkeypatch) -> None:
    monkeypatch.delenv("FLICKIES_RATE_LIMIT_PER_MIN", raising=False)
    from flickies.server import build_app

    c = TestClient(build_app())
    r = c.get("/v1/health")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid and len(rid) >= 16


def test_request_id_echoed_when_provided(base_env, monkeypatch) -> None:
    monkeypatch.delenv("FLICKIES_RATE_LIMIT_PER_MIN", raising=False)
    from flickies.server import build_app

    c = TestClient(build_app())
    r = c.get("/v1/health", headers={"X-Request-Id": "my-correlator-123"})
    assert r.headers.get("x-request-id") == "my-correlator-123"


def test_rate_limit_429_after_capacity(base_env, monkeypatch) -> None:
    monkeypatch.setenv("FLICKIES_RATE_LIMIT_PER_MIN", "2")
    from flickies.server import build_app

    c = TestClient(build_app())
    assert c.get("/v1/health").status_code == 200
    assert c.get("/v1/health").status_code == 200
    r = c.get("/v1/health")
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == "RATE_LIMITED"
    assert "retry-after" in {k.lower() for k in r.headers.keys()}


def test_healthz_exempt_from_rate_limit(base_env, monkeypatch) -> None:
    monkeypatch.setenv("FLICKIES_RATE_LIMIT_PER_MIN", "1")
    from flickies.server import build_app

    c = TestClient(build_app())
    # First call burns the bucket for /v1/health.
    assert c.get("/v1/health").status_code == 200
    assert c.get("/v1/health").status_code == 429
    # /healthz is exempt.
    for _ in range(5):
        assert c.get("/healthz").status_code == 200


def test_rate_limit_disabled_with_zero(base_env, monkeypatch) -> None:
    monkeypatch.setenv("FLICKIES_RATE_LIMIT_PER_MIN", "0")
    from flickies.server import build_app

    c = TestClient(build_app())
    for _ in range(20):
        assert c.get("/v1/health").status_code == 200


def test_idempotency_replays_response(base_env, monkeypatch) -> None:
    monkeypatch.delenv("FLICKIES_RATE_LIMIT_PER_MIN", raising=False)
    from flickies.server import build_app

    c = TestClient(build_app())
    # PUT a file to set up a unique state, then POST trim with idempotency-key.
    c.put("/v1/files/uploads/dummy.bin", content=b"x" * 100)

    # First call: 400 because trim args invalid (no real video).
    r1 = c.post(
        "/v1/video/trim",
        json={
            "file_path": "uploads/dummy.bin",
            "start_sec": 1.0,
            "end_sec": 0.5,
            "output_path": "out.mp4",
        },
        headers={"Idempotency-Key": "abc-key-1"},
    )
    # Second call should return the same response (replayed from cache).
    r2 = c.post(
        "/v1/video/trim",
        json={
            "file_path": "uploads/dummy.bin",
            "start_sec": 999.0,
            "end_sec": 998.0,
            "output_path": "completely-different.mp4",
        },
        headers={"Idempotency-Key": "abc-key-1"},
    )
    assert r1.status_code == r2.status_code
    assert r1.content == r2.content
