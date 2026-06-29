"""FastAPI app — every route declared in openapi.yaml.

Handlers stay thin: validate xor-inputs/outputs, fetch URL inputs to a
temp file via flickies.fetch, dispatch to the engine via the registry
(which handles hot-swap eviction), write outputs via flickies.files or
flickies.fetch.put_file, and return the canonical StagedOutputResponse
or UrlOutputResponse shape.

Async-job mode: any video-producing endpoint with `async_job=true`
returns 202 + {job_id} immediately; the work runs in a background task
via flickies.jobs.JobQueue. Poll `GET /v1/jobs/{job_id}`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from flickies import __version__
from flickies.auth import BearerAuthMiddleware
from flickies.config import Config, load
from flickies.engines._license_gate import NonCommercialOptInRequired, noncommercial_enabled
from flickies.engines._registry import EngineNotRegistered, Registry
from flickies.engines.gfpgan import GFPGAN
from flickies.engines.latentsync import LatentSync
from flickies.engines.wav2lip import Wav2Lip
from flickies.ffmpeg import FFmpeg
from flickies.errors import (
    CODE_BAD_REQUEST,
    CODE_ENGINE_NOT_REGISTERED,
    CODE_INTERNAL,
    CODE_NONCOMMERCIAL_GATE_REFUSED,
    CODE_NOT_FOUND,
    CODE_VALIDATION_FAILED,
    http_error,
)
from flickies.files import (
    delete as delete_file,
    files_dir,
    resolve_safe,
    save_stream,
    stream_file,
)
from flickies.fetch import fetch_to_temp, put_file
from flickies.jobs import JobQueue
from flickies.middleware import (
    IdempotencyMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
)


_log = logging.getLogger("flickies.server")


_EXECUTOR_MAP: dict[str, type] = {
    "wav2lip": Wav2Lip,
    "latentsync": LatentSync,
    "gfpgan": GFPGAN,
}


def _build_registry(cfg: Config) -> Registry:
    r = Registry()
    for slug, spec in cfg.engines.items():
        executor = spec.get("executor")
        cls = _EXECUTOR_MAP.get(executor) if isinstance(executor, str) else None
        if cls is None:
            _log.warning("engine skipped — unknown executor", extra={"engine_slug": slug, "executor": str(executor), "reason": "unknown_executor"})
            continue
        r.register(cls(slug=slug, **spec))
    return r


# ── input/output helpers ────────────────────────────────────────────────

async def _resolve_input(
    cfg: Config,
    *,
    file_path: str | None,
    file_url: str | None,
    suffix: str = ".mp4",
) -> tuple[Path, bool]:
    """Return (local_path, is_tempfile). is_tempfile callers should unlink."""
    n = int(bool(file_path)) + int(bool(file_url))
    if n != 1:
        raise http_error(
            400, CODE_BAD_REQUEST,
            "must provide exactly one of: file_path, file_url",
        )
    if file_path:
        return resolve_safe(files_dir(cfg.data_dir), file_path), False
    assert file_url is not None
    tmp = await fetch_to_temp(file_url, suffix=suffix)
    return tmp, True


def _validate_output_xor(
    output_path: str | None,
    output_url: str | None,
    *,
    async_job: bool,
) -> None:
    has_path = bool(output_path)
    has_url = bool(output_url)
    if has_path and has_url:
        raise http_error(400, CODE_BAD_REQUEST, "output_path and output_url are mutually exclusive")
    if async_job:
        return
    if not has_path and not has_url:
        raise http_error(
            400, CODE_BAD_REQUEST,
            "video-producing endpoint requires output_path or output_url "
            "(or set async_job=true)",
        )


async def _finalise_output(
    cfg: Config,
    tmp: Path,
    *,
    output_path: str | None,
    output_url: str | None,
) -> dict[str, Any]:
    """Move temp output to its destination + return the response payload."""
    size = tmp.stat().st_size
    if output_path:
        dst = resolve_safe(files_dir(cfg.data_dir), output_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(dst))
        return {"path": output_path, "size": size}
    if output_url:
        try:
            await put_file(tmp, output_url)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        return {"url": output_url, "size": size}
    # Async-staged path: caller passed neither; the route handler picked a
    # jobs/<id>.<ext> path before calling. Treat tmp as the final result;
    # the caller-supplied dst will be passed via output_path in that case.
    # (We never reach here with both empty in the sync path because
    # _validate_output_xor would have rejected.)
    raise http_error(500, CODE_INTERNAL, "neither output_path nor output_url provided")


def _async_staged_path(_cfg: Config, ext: str, job_id: str) -> str:
    """Generate the relative jobs/<id>.<ext> staging path for async jobs."""
    return f"jobs/{job_id}.{ext.lstrip('.')}"


# ── app factory ─────────────────────────────────────────────────────────

def build_app() -> FastAPI:
    cfg = load()
    registry = _build_registry(cfg)
    job_queue = JobQueue()
    ffmpeg = FFmpeg()  # plain singleton — NOT in the registry. Not an engine.

    # Construct the MCP server (if mcp installed) so the lifespan can drive
    # its session_manager. None when mcp isn't available.
    mcp_server: Any = None
    try:
        from flickies.mcp_server import build_mcp_server
        mcp_server = build_mcp_server(cfg=cfg, registry=registry, ffmpeg=ffmpeg)
    except ImportError as e:
        _log.warning("mcp server unavailable", extra={"err": str(e), "reason": "import_failed"})

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        _ = _app
        registry.start_sweeper()
        try:
            if mcp_server is not None:
                # FastMCP's streamable-HTTP session manager needs to live
                # inside the app's lifespan task group. Without this, every
                # /v1/mcp request raises "Task group is not initialized".
                async with mcp_server.session_manager.run():
                    yield
            else:
                yield
        finally:
            await registry.stop_sweeper()

    app = FastAPI(title="flickies", version=__version__, lifespan=lifespan)
    app.state.cfg = cfg
    app.state.registry = registry
    app.state.jobs = job_queue
    app.state.ffmpeg = ffmpeg

    # Middleware order: outermost → innermost is the order of add_middleware
    # *reversed*. We want:  RequestId(outer) → RateLimit → Idempotency → Auth → app.
    # So we add Auth first (innermost) and RequestId last (outermost).
    token = os.environ.get("FLICKIES_AUTH_TOKEN", "")
    if token:
        app.add_middleware(BearerAuthMiddleware, token=token)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)

    if mcp_server is not None:
        app.mount("/v1/mcp", mcp_server.streamable_http_app())

    # ── error envelope shaping ─────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            payload = detail
        else:
            payload = {
                "code": _status_to_code(exc.status_code),
                "message": str(detail),
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(NonCommercialOptInRequired)
    async def _nc_exc(_req: Request, exc: NonCommercialOptInRequired) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "code": CODE_NONCOMMERCIAL_GATE_REFUSED,
                "message": str(exc),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_req: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": CODE_VALIDATION_FAILED,
                "message": "request body failed validation",
                "details": {"errors": exc.errors()},
            },
        )

    # ── /healthz (unversioned, exempt from auth) ──────────────────────
    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    # ── /v1/health ─────────────────────────────────────────────────────
    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        try:
            ffmpeg_version = await ffmpeg.version()
        except Exception:  # noqa: BLE001
            ffmpeg_version = None
        return {
            "status": "ok",
            "version": __version__,
            "device": cfg.device,
            "ffmpeg": ffmpeg_version,
            "available_engines": sorted(cfg.engines.keys()),
            "enabled_engines": sorted(cfg.enabled_engines),
            "loaded_engine": registry.loaded_slug(),
            "noncommercial_enabled": noncommercial_enabled(),
        }

    # ── /v1/engines ────────────────────────────────────────────────────
    @app.get("/v1/engines")
    async def list_engines() -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for slug in registry.slugs():
            eng = registry.get(slug)
            spec = eng.spec
            out.append({
                "slug": slug,
                "executor": spec.get("executor", ""),
                "variant": spec.get("variant"),
                "loaded": eng.loaded(),
                "noncommercial": bool(spec.get("noncommercial", False)),
                "cuda_only": bool(spec.get("cuda_only", False)),
                "vram_gb_min": spec.get("vram_gb_min"),
                "description": spec.get("description", ""),
                "last_used_secs_ago": eng.last_used_secs_ago(),
            })
        return {"engines": out}

    @app.delete("/v1/engines/{slug}")
    async def evict_engine(slug: str) -> Response:
        try:
            eng = registry.get(slug)
        except EngineNotRegistered as e:
            raise http_error(404, CODE_ENGINE_NOT_REGISTERED, str(e)) from e
        await eng.unload()
        return Response(status_code=204)

    # ── /v1/files/{path} (PUT / GET / DELETE) ──────────────────────────
    @app.put("/v1/files/{path:path}", status_code=201)
    async def put_file_route(path: str, request: Request) -> dict[str, Any]:
        dst = resolve_safe(files_dir(cfg.data_dir), path)
        size, sha = await save_stream(dst, request.stream())
        return {"path": path, "size": size, "sha256": sha}

    @app.get("/v1/files/{path:path}")
    async def get_file_route(path: str) -> StreamingResponse:
        src = resolve_safe(files_dir(cfg.data_dir), path)
        if not src.exists():
            raise http_error(404, CODE_NOT_FOUND, f"file not found: {path}")
        return StreamingResponse(stream_file(src), media_type="application/octet-stream")

    @app.delete("/v1/files/{path:path}")
    async def delete_file_route(path: str) -> Response:
        src = resolve_safe(files_dir(cfg.data_dir), path)
        delete_file(src)
        return Response(status_code=204)

    # ── /v1/jobs/{job_id} ──────────────────────────────────────────────
    @app.get("/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        job = await job_queue.get(job_id)
        if job is None:
            raise http_error(404, CODE_NOT_FOUND, f"job not found: {job_id}")
        return job.to_dict()

    # ── helpers used by all video-producing routes ─────────────────────
    async def _run_or_schedule(
        body: dict[str, Any],
        ext: str,
        work: Callable[[Path], "asyncio.Future[Any] | Any"],
    ) -> tuple[int, dict[str, Any]]:
        """Either runs `work(tmp_output_path)` inline or schedules async.

        Returns (status_code, payload).
        """
        output_path = body.get("output_path")
        output_url = body.get("output_url")
        async_job = bool(body.get("async_job", False))
        _validate_output_xor(output_path, output_url, async_job=async_job)

        if async_job:
            webhook_url = body.get("webhook_url")
            # Pre-allocate the job id so the staged path includes it.
            import uuid as _uuid
            preallocated_id = str(_uuid.uuid4())

            async def runner() -> dict[str, Any]:
                tmp = Path(tempfile.mkstemp(prefix="flickies-out-", suffix=f".{ext}")[1])
                try:
                    await _maybe_await(work(tmp))
                    job_path = _async_staged_path(cfg, ext, preallocated_id)
                    dst = resolve_safe(files_dir(cfg.data_dir), job_path)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(tmp), str(dst))
                    return {"path": job_path, "size": dst.stat().st_size}
                finally:
                    if tmp.exists():
                        try:
                            tmp.unlink()
                        except OSError:
                            pass

            job = await job_queue.submit(runner, webhook_url=webhook_url)
            return 202, {"job_id": job.job_id, "status": "accepted"}

        # Sync path.
        with tempfile.NamedTemporaryFile(prefix="flickies-out-", suffix=f".{ext}", delete=False) as f:
            tmp = Path(f.name)
        try:
            await _maybe_await(work(tmp))
            payload = await _finalise_output(
                cfg, tmp,
                output_path=output_path,
                output_url=output_url,
            )
            return 200, payload
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    async def _maybe_await(x: Any) -> Any:
        if asyncio.iscoroutine(x) or asyncio.isfuture(x):
            return await x
        return x

    # ── /v1/video/lipsync ──────────────────────────────────────────────
    @app.post("/v1/video/lipsync")
    async def post_lipsync(body: dict[str, Any]) -> JSONResponse:
        engine_slug = body.get("engine") or "latentsync-1.5"
        try:
            eng = await registry.acquire(engine_slug)
        except EngineNotRegistered as e:
            raise http_error(404, CODE_ENGINE_NOT_REGISTERED, str(e)) from e

        face_tmp_to_clean: list[Path] = []
        async def work(out: Path) -> None:
            face, face_tmp = await _resolve_input(
                cfg,
                file_path=body.get("face_path"),
                file_url=body.get("face_url"),
                suffix=".mp4",
            )
            if face_tmp:
                face_tmp_to_clean.append(face)
            audio_path = body.get("audio_path")
            audio_url = body.get("audio_url")
            n_audio = int(bool(audio_path)) + int(bool(audio_url))
            if n_audio != 1:
                raise http_error(
                    400, CODE_BAD_REQUEST,
                    "must provide exactly one of: audio_path, audio_url",
                )
            if audio_url:
                audio = await fetch_to_temp(audio_url, suffix=".wav")
                face_tmp_to_clean.append(audio)
            else:
                assert audio_path is not None
                audio = resolve_safe(files_dir(cfg.data_dir), audio_path)
            await eng.lipsync(face, audio, out)  # type: ignore[attr-defined]

        try:
            status, payload = await _run_or_schedule(body, "mp4", work)
        finally:
            for p in face_tmp_to_clean:
                try:
                    p.unlink()
                except OSError:
                    pass
        return JSONResponse(status_code=status, content=payload)

    # ── /v1/video/restore (GFPGAN) ─────────────────────────────────────
    @app.post("/v1/video/restore")
    async def post_restore(body: dict[str, Any]) -> JSONResponse:
        try:
            eng = await registry.acquire("gfpgan")
        except EngineNotRegistered as e:
            raise http_error(404, CODE_ENGINE_NOT_REGISTERED, str(e)) from e

        tmp_to_clean: list[Path] = []
        async def work(out: Path) -> None:
            src, is_tmp = await _resolve_input(
                cfg,
                file_path=body.get("file_path"),
                file_url=body.get("file_url"),
            )
            if is_tmp:
                tmp_to_clean.append(src)
            await eng.restore(src, out)  # type: ignore[attr-defined]

        try:
            status, payload = await _run_or_schedule(body, "mp4", work)
        finally:
            for p in tmp_to_clean:
                try:
                    p.unlink()
                except OSError:
                    pass
        return JSONResponse(status_code=status, content=payload)

    # ── helper for ffmpeg-driven routes (uses the singleton, not registry) ──
    async def _ffmpeg_handler(
        body: dict[str, Any],
        ext: str,
        op_factory: Callable[[FFmpeg, Path, Path], "asyncio.Future[Any] | Any"],
    ) -> JSONResponse:
        tmp_to_clean: list[Path] = []

        async def work(out: Path) -> None:
            src, is_tmp = await _resolve_input(
                cfg,
                file_path=body.get("file_path"),
                file_url=body.get("file_url"),
            )
            if is_tmp:
                tmp_to_clean.append(src)
            await _maybe_await(op_factory(ffmpeg, src, out))

        try:
            status, payload = await _run_or_schedule(body, ext, work)
        finally:
            for p in tmp_to_clean:
                try:
                    p.unlink()
                except OSError:
                    pass
        return JSONResponse(status_code=status, content=payload)

    # ── ffmpeg-ops routes ──────────────────────────────────────────────
    @app.post("/v1/video/trim")
    async def post_trim(body: dict[str, Any]) -> JSONResponse:
        return await _ffmpeg_handler(
            body, "mp4",
            lambda eng, src, out: eng.trim(
                src, out,
                float(body["start_sec"]),
                float(body["end_sec"]),
                precise=bool(body.get("precise", False)),
            ),
        )

    @app.post("/v1/video/concat")
    async def post_concat(body: dict[str, Any]) -> JSONResponse:
        inputs_paths = body.get("inputs_paths") or []
        inputs_urls = body.get("inputs_urls") or []
        if bool(inputs_paths) == bool(inputs_urls):
            raise http_error(400, CODE_BAD_REQUEST, "exactly one of inputs_paths / inputs_urls required")

        tmp_to_clean: list[Path] = []

        precise = bool(body.get("precise", False))

        async def work(out: Path) -> None:
            if inputs_urls:
                resolved: list[Path] = []
                for url in inputs_urls:
                    t = await fetch_to_temp(url, suffix=".mp4")
                    resolved.append(t)
                    tmp_to_clean.append(t)
                await ffmpeg.concat(resolved, out, precise=precise)
            else:
                resolved = [resolve_safe(files_dir(cfg.data_dir), p) for p in inputs_paths]
                await ffmpeg.concat(resolved, out, precise=precise)

        try:
            status, payload = await _run_or_schedule(body, "mp4", work)
        finally:
            for p in tmp_to_clean:
                try:
                    p.unlink()
                except OSError:
                    pass
        return JSONResponse(status_code=status, content=payload)

    @app.post("/v1/video/transcode")
    async def post_transcode(body: dict[str, Any]) -> JSONResponse:
        ext = body.get("output_format", "mp4")
        return await _ffmpeg_handler(
            body, ext,
            lambda eng, src, out: eng.transcode(
                src, out,
                output_format=ext,
                video_codec=body.get("video_codec"),
                audio_codec=body.get("audio_codec"),
                crf=body.get("crf"),
                preset=body.get("preset"),
                fps=body.get("fps"),
                gif_options=body.get("gif_options"),
            ),
        )

    @app.post("/v1/video/scale")
    async def post_scale(body: dict[str, Any]) -> JSONResponse:
        return await _ffmpeg_handler(
            body, "mp4",
            lambda eng, src, out: eng.scale(
                src, out,
                width=int(body["width"]),
                height=int(body["height"]),
                keep_aspect=bool(body.get("keep_aspect", True)),
            ),
        )

    @app.post("/v1/video/mux_audio")
    async def post_mux_audio(body: dict[str, Any]) -> JSONResponse:
        tmp_to_clean: list[Path] = []

        async def _resolve_or_url(spec: str, suffix: str) -> Path:
            if spec.startswith(("http://", "https://")):
                t = await fetch_to_temp(spec, suffix=suffix)
                tmp_to_clean.append(t)
                return t
            return resolve_safe(files_dir(cfg.data_dir), spec)

        async def work(out: Path) -> None:
            video = await _resolve_or_url(body["video_path_or_url"], ".mp4")
            audio = await _resolve_or_url(body["audio_path_or_url"], ".wav")
            await ffmpeg.mux_audio(
                video, audio, out,
                replace_existing_audio=bool(body.get("replace_existing_audio", True)),
            )

        try:
            status, payload = await _run_or_schedule(body, "mp4", work)
        finally:
            for p in tmp_to_clean:
                try:
                    p.unlink()
                except OSError:
                    pass
        return JSONResponse(status_code=status, content=payload)

    @app.post("/v1/video/extract_audio")
    async def post_extract_audio(body: dict[str, Any]) -> JSONResponse:
        audio_format = body.get("audio_format", "wav")
        return await _ffmpeg_handler(
            body, audio_format,
            lambda eng, src, out: eng.extract_audio(src, out, audio_format),
        )

    @app.post("/v1/video/thumbnail_grid")
    async def post_thumbnail_grid(body: dict[str, Any]) -> JSONResponse:
        return await _ffmpeg_handler(
            body, "png",
            lambda eng, src, out: eng.thumbnail_grid(
                src, out,
                rows=int(body["rows"]),
                cols=int(body["cols"]),
                cell_width=int(body.get("cell_width", 320)),
                cell_height=int(body.get("cell_height", 180)),
            ),
        )

    @app.post("/v1/video/info")
    async def post_info(body: dict[str, Any]) -> dict[str, Any]:
        src, is_tmp = await _resolve_input(
            cfg,
            file_path=body.get("file_path"),
            file_url=body.get("file_url"),
        )
        try:
            return await ffmpeg.info(src)
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass

    return app


def _status_to_code(status: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_FAILED",
        500: "INTERNAL_SERVER_ERROR",
        502: "UPSTREAM_FETCH_FAILED",
    }.get(status, "ERROR")
