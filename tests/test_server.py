"""End-to-end-ish server tests via fastapi.testclient.

ML engines (Wav2Lip, LatentSync, GFPGAN) stay stubbed — these tests cover
the routing layer, error envelope shape, auth, file staging, jobs,
ffmpeg singleton helper (which actually shells out to ffmpeg if available),
and the non-commercial gate refusal.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import subprocess
import time
import zipfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from flickies.engines.base import Engine

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app_client(monkeypatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLICKIES_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FLICKIES_ENABLE_NONCOMMERCIAL", raising=False)
    from flickies.server import build_app

    with TestClient(build_app()) as client:
        yield client


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


class BlockingRestore(Engine):
    def __init__(self, slug: str, **spec):
        super().__init__(slug, **spec)
        self.ready = False

    def loaded(self) -> bool:
        return self.ready

    async def health(self) -> dict:
        return {"loaded": self.ready}

    async def restore(self, src: Path, dst: Path) -> None:
        if src.name == "invalid.mp4":
            raise HTTPException(status_code=400, detail="invalid test video")
        self.ready = True
        src.with_name("worker-started").touch()
        deadline = time.monotonic() + 5
        while not src.with_name("worker-release").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("worker test was not released")
            await asyncio.sleep(0.01)
        dst.write_text(str(os.getpid()))


def test_unload_conflict_and_worker_exit(monkeypatch, tmp_path: Path) -> None:
    from flickies import server

    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLICKIES_AUTH_TOKEN", raising=False)
    monkeypatch.setitem(server._EXECUTOR_MAP, "gfpgan", BlockingRestore)

    with TestClient(server.build_app()) as client, ThreadPoolExecutor(max_workers=1) as threads:
        assert client.post("/v1/unload").json() == {"unloaded": []}
        assert client.put("/v1/files/invalid.mp4", content=b"invalid").status_code == 201
        invalid = client.post(
            "/v1/video/restore",
            json={"file_path": "invalid.mp4", "output_path": "output.mp4"},
        )
        assert invalid.status_code == 400
        assert invalid.json()["message"] == "invalid test video"
        assert client.put("/v1/files/input.mp4", content=b"test").status_code == 201
        future = threads.submit(
            client.post,
            "/v1/video/restore",
            json={"file_path": "input.mp4", "output_path": "output.mp4"},
        )
        files = tmp_path / "files"
        try:
            for _ in range(500):
                if (files / "worker-started").exists():
                    break
                time.sleep(0.01)
            assert (files / "worker-started").exists()
            assert client.post("/v1/unload").status_code == 409
            assert client.delete("/v1/engines/gfpgan").status_code == 409
        finally:
            (files / "worker-release").touch()

        assert future.result(timeout=5).status_code == 200
        pid = int(client.get("/v1/files/output.mp4").content)
        assert pid != os.getpid()
        assert client.post("/v1/unload").json() == {"unloaded": ["gfpgan"]}
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        assert client.post("/v1/unload").json() == {"unloaded": []}


def test_list_engines(app_client: TestClient) -> None:
    r = app_client.get("/v1/engines")
    assert r.status_code == 200
    engines = {e["slug"]: e for e in r.json()["engines"]}
    assert engines["wav2lip"]["noncommercial"] is True
    assert engines["latentsync-1.5"]["noncommercial"] is False
    assert "ffmpeg-ops" not in engines  # ffmpeg is NOT an engine
    assert "ffprobe" not in engines  # nor is ffprobe


def test_auth_blocks_without_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLICKIES_ENGINES_FILE", str(REPO_ROOT / "engines.json"))
    monkeypatch.setenv("FLICKIES_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLICKIES_AUTH_TOKEN", "secret-token")
    from flickies.server import build_app

    c = TestClient(build_app())
    r = c.get("/v1/health")
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHORIZED"
    assert c.post("/v1/unload").status_code == 401

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
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=128x96:rate=10",
            "-pix_fmt",
            "yuv420p",
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
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=128x96:rate=10",
            "-pix_fmt",
            "yuv420p",
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


@pytest.fixture
def edit_inputs(app_client: TestClient, tmp_path: Path) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    fixtures = {
        "cuts.mp4": [
            "-f",
            "lavfi",
            "-i",
            "color=black:s=160x96:r=20:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=160x96:r=20:d=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "2:a",
            "-shortest",
        ],
        "other.mp4": ["-f", "lavfi", "-i", "testsrc2=s=128x72:r=25:d=2"],
    }
    for name, args in fixtures.items():
        output = tmp_path / name
        subprocess.run(
            ["ffmpeg", "-v", "error", *args, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)],
            check=True,
            capture_output=True,
        )
        assert app_client.put(f"/v1/files/{name}", content=output.read_bytes()).is_success
    assert app_client.put(
        "/v1/files/test.srt", content=b"1\n00:00:00,200 --> 00:00:01,000\nFlickies captions\n"
    ).is_success


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("subtitles", {"subtitle_path": "test.srt"}),
        ("subtitles", {"subtitle_path": "test.srt", "mode": "embed"}),
        (
            "subtitles",
            {
                "words": [
                    {"text": "One", "start_sec": 0.1, "end_sec": 0.5},
                    {"text": "two", "start_sec": 0.6, "end_sec": 0.9},
                ]
            },
        ),
        ("crop", {"width": 80, "height": 80, "mode": "blur"}),
        ("crop", {"width": 80, "height": 80, "x": 30, "y": 4}),
        ("overlay", {"text": "100% video", "end_sec": 1}),
        ("compose", {"second_path": "other.mp4", "width": 160, "height": 96}),
        ("transcode", {"max_size_bytes": 65536}),
    ],
)
def test_new_video_exports(
    app_client: TestClient, edit_inputs: None, operation: str, options: dict
) -> None:
    _ = edit_inputs
    response = app_client.post(
        f"/v1/video/{operation}",
        json={"file_path": "cuts.mp4", "output_path": "edited.mp4", **options},
    )
    assert response.status_code == 200, response.text
    assert response.json()["size"] > 0
    if "max_size_bytes" in options:
        assert response.json()["size"] <= options["max_size_bytes"]
    if operation == "crop":
        info = app_client.post("/v1/video/info", json={"file_path": "edited.mp4"}).json()
        assert (info["width"], info["height"]) == (80, 80)


@pytest.mark.parametrize("join", ["fade", "cut"])
def test_concat_transition(app_client: TestClient, edit_inputs: None, join: str) -> None:
    _ = edit_inputs
    response = app_client.post(
        "/v1/video/concat",
        json={
            "inputs_paths": ["cuts.mp4", "other.mp4", "cuts.mp4"],
            "transitions": [
                {"effect": join, "duration_sec": 0.25 if join == "fade" else 0},
                {"effect": "wipeleft", "duration_sec": 0.25},
            ],
            "output_path": "joined.mp4",
        },
    )
    assert response.status_code == 200, response.text
    info = app_client.post("/v1/video/info", json={"file_path": "joined.mp4"}).json()
    assert info["duration_sec"] == pytest.approx(5.5 if join == "fade" else 5.75, abs=0.11)
    assert info["audio_codec"] == "aac"


def test_analysis_outputs(app_client: TestClient, edit_inputs: None) -> None:
    _ = edit_inputs
    response = app_client.post(
        "/v1/video/scenes",
        json={"file_path": "cuts.mp4", "artifacts": "frames", "output_path": "shots.zip"},
    )
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(app_client.get("/v1/files/shots.zip").content)) as archive:
        shots = json.loads(archive.read("scenes.json"))["scenes"]
        assert len(shots) == 2
        assert shots[1]["start_sec"] == pytest.approx(1)
        assert "scene-002.jpg" in archive.namelist()

    response = app_client.post(
        "/v1/video/analyze", json={"file_path": "cuts.mp4", "output_path": "report.json"}
    )
    assert response.status_code == 200, response.text
    events = app_client.get("/v1/files/report.json").json()["events"]
    assert {"black", "freeze", "silence"} == {event["kind"] for event in events}

    response = app_client.post(
        "/v1/video/frames",
        json={
            "file_path": "cuts.mp4",
            "sample_interval_sec": 0.5,
            "max_frames": 3,
            "async_job": True,
        },
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    for _ in range(100):
        poll = app_client.get(f"/v1/jobs/{job_id}")
        assert poll.status_code == 200, poll.text
        job = poll.json()
        if job["status"] in {"complete", "failed"}:
            break
        time.sleep(0.025)
    assert job["status"] == "complete", job
    with zipfile.ZipFile(
        io.BytesIO(app_client.get("/v1/files/" + job["result"]["path"]).content)
    ) as archive:
        frames = json.loads(archive.read("frames.json"))["frames"]
        assert [frame["time_sec"] for frame in frames] == pytest.approx([0, 0.5, 1])
        assert all(archive.read(frame["file"]).startswith(b"\xff\xd8") for frame in frames)

    response = app_client.post(
        "/v1/video/thumbnail_grid",
        json={
            "file_path": "cuts.mp4",
            "rows": 2,
            "cols": 2,
            "cell_width": 80,
            "cell_height": 64,
            "timestamps": True,
            "layout": "review",
            "output_path": "grid.png",
        },
    )
    assert response.status_code == 200, response.text
    assert app_client.get("/v1/files/grid.png").content.startswith(b"\x89PNG")


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("overlay", {"text": "@file", "end_sec": 1}),
        ("overlay", {"image_path": "../image.png", "end_sec": 1}),
        ("subtitles", {"subtitle_path": "../secret.srt"}),
        ("subtitles", {"words": [{"text": "hi", "start_sec": 2, "end_sec": 1}]}),
        ("crop", {"width": 17, "height": 80}),
        ("compose", {"second_path": "../secret.mp4"}),
        ("scenes", {"max_scenes": 300}),
        ("frames", {"sample_interval_sec": 0}),
    ],
)
def test_edit_invalid_input(app_client: TestClient, operation: str, options: dict) -> None:
    response = app_client.post(
        f"/v1/video/{operation}",
        json={"file_path": "test.mp4", "output_path": "out/file", **options},
    )
    assert response.status_code == 400, response.text


def test_new_tools_over_mcp(app_client: TestClient, edit_inputs: None) -> None:
    _ = edit_inputs
    headers = {"Host": "localhost:8000", "Accept": "application/json, text/event-stream"}
    tools = app_client.post(
        "/v1/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        },
    )
    assert tools.status_code == 200, tools.text
    assert len(tools.json()["result"]["tools"]) == 18
    reply = app_client.post(
        "/v1/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "frames",
                "arguments": {
                    "file_path": "cuts.mp4",
                    "max_frames": 1,
                    "output_path": "mcp.zip",
                },
            },
        },
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["result"]["structuredContent"]["path"] == "mcp.zip"


def test_missing_overlay_asset(app_client: TestClient) -> None:
    response = app_client.post(
        "/v1/video/overlay",
        json={
            "file_path": "video.mp4",
            "image_path": "missing.png",
            "end_sec": 1,
            "output_path": "out.mp4",
        },
    )
    assert response.status_code == 404, response.text
