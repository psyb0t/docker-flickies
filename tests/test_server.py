"""End-to-end-ish server tests via fastapi.testclient.

ML engines (Wav2Lip, LatentSync, GFPGAN) stay stubbed — these tests cover
the routing layer, error envelope shape, auth, file staging, jobs,
ffmpeg singleton helper (which actually shells out to ffmpeg if available),
and the non-commercial gate refusal.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLICKIES_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FLICKIES_ENABLE_NONCOMMERCIAL", raising=False)
    from flickies.server import build_app
    return TestClient(build_app())


def test_healthz_open(app_client: TestClient) -> None:
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_v1_health_shape(app_client: TestClient) -> None:
    r = app_client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "available_engines" in body
    assert "noncommercial_enabled" in body
    assert body["noncommercial_enabled"] is False
    assert "wav2lip" in body["available_engines"]


def test_list_engines(app_client: TestClient) -> None:
    r = app_client.get("/v1/engines")
    assert r.status_code == 200
    engines = {e["slug"]: e for e in r.json()["engines"]}
    assert engines["wav2lip"]["noncommercial"] is True
    assert engines["latentsync-1.5"]["noncommercial"] is False
    assert "ffmpeg-ops" not in engines  # ffmpeg is NOT an engine
    assert "ffprobe" not in engines     # nor is ffprobe


def test_auth_blocks_without_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLICKIES_AUTH_TOKEN", "secret-token")
    from flickies.server import build_app

    c = TestClient(build_app())
    r = c.get("/v1/health")
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHORIZED"

    # /healthz is still open.
    assert c.get("/healthz").status_code == 200

    # With token works.
    r = c.get("/v1/health", headers={"Authorization": "Bearer secret-token"})
    assert r.status_code == 200


def test_lipsync_refused_without_noncommercial_optin(app_client: TestClient) -> None:
    r = app_client.post(
        "/v1/video/lipsync",
        json={
            "face_path": "doesnt-exist.mp4",
            "audio_path": "doesnt-exist.wav",
            "engine": "wav2lip",
            "output_path": "out.mp4",
        },
    )
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "NONCOMMERCIAL_GATE_REFUSED"
    assert "FLICKIES_ENABLE_NONCOMMERCIAL" in body["message"]


def test_files_put_get_delete_roundtrip(app_client: TestClient) -> None:
    payload = b"hello flickies " * 100
    r = app_client.put("/v1/files/uploads/test.bin", content=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["size"] == len(payload)
    assert len(body["sha256"]) == 64

    r = app_client.get("/v1/files/uploads/test.bin")
    assert r.status_code == 200
    assert r.content == payload

    r = app_client.delete("/v1/files/uploads/test.bin")
    assert r.status_code == 204

    r = app_client.get("/v1/files/uploads/test.bin")
    assert r.status_code == 404


def test_path_traversal_blocked(app_client: TestClient) -> None:
    r = app_client.put("/v1/files/../../etc/passwd", content=b"x")
    # FastAPI's path:path normalises this; the resolver still blocks it.
    assert r.status_code in (400, 404)


def test_validate_output_xor_rejects_both(app_client: TestClient) -> None:
    r = app_client.post(
        "/v1/video/trim",
        json={
            "file_path": "in.mp4",
            "start_sec": 0.0,
            "end_sec": 1.0,
            "output_path": "out.mp4",
            "output_url": "http://example.com/out.mp4",
        },
    )
    assert r.status_code == 400
    assert "mutually exclusive" in r.json()["message"]


def test_validate_output_xor_rejects_neither(app_client: TestClient) -> None:
    r = app_client.post(
        "/v1/video/trim",
        json={"file_path": "in.mp4", "start_sec": 0.0, "end_sec": 1.0},
    )
    assert r.status_code == 400


def test_evict_unknown_engine_returns_404(app_client: TestClient) -> None:
    r = app_client.delete("/v1/engines/does-not-exist")
    assert r.status_code == 404
    assert r.json()["code"] == "ENGINE_NOT_REGISTERED"


def test_get_unknown_job_returns_404(app_client: TestClient) -> None:
    r = app_client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_info_roundtrip_with_real_ffmpeg(app_client: TestClient, tmp_path: Path) -> None:
    """Generate a 1s synthetic test pattern, query /v1/video/info, assert metadata."""
    # Stage a real MP4 inside the configured data dir's files/ subdir.
    files_root = tmp_path / "files" / "samples"
    files_root.mkdir(parents=True, exist_ok=True)
    src = files_root / "tone.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=128x96:rate=10",
            "-pix_fmt", "yuv420p",
            str(src),
        ],
        check=True,
    )

    r = app_client.post(
        "/v1/video/info",
        json={"file_path": "samples/tone.mp4"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["width"] == 128
    assert body["height"] == 96
    assert body["duration_sec"] == pytest.approx(1.0, abs=0.1)
    assert body["video_codec"] in ("h264", "mpeg4")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_trim_with_real_ffmpeg(app_client: TestClient, tmp_path: Path) -> None:
    """Trim a 2s clip down to 1s, assert output exists + duration."""
    files_root = tmp_path / "files" / "samples"
    files_root.mkdir(parents=True, exist_ok=True)
    src = files_root / "tone.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=128x96:rate=10",
            "-pix_fmt", "yuv420p",
            str(src),
        ],
        check=True,
    )

    r = app_client.post(
        "/v1/video/trim",
        json={
            "file_path": "samples/tone.mp4",
            "start_sec": 0.0,
            "end_sec": 1.0,
            "output_path": "out/trimmed.mp4",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] == "out/trimmed.mp4"
    assert body["size"] > 0
    assert (tmp_path / "files" / "out" / "trimmed.mp4").is_file()
