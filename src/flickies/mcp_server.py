"""MCP server for flickies — mounted at `/v1/mcp` on the main FastAPI app.

Exposes the same surface as the HTTP REST API as MCP tools so an agent
(LibreChat / Claude / etc.) can drive flickies over JSON-RPC / streamable-HTTP.

Tools:
  - list_engines        — what engines are loaded/loadable
  - lipsync             — Wav2Lip / LatentSync (face + audio → mp4)
  - restore             — GFPGAN face restore on a video
  - transcode           — universal re-encode (mp4 / webm / mov / mkv / gif)
  - trim, concat        — basic edits
  - scale, mux_audio    — dimension change + audio replacement
  - extract_audio       — pull audio track out as wav/mp3/m4a/ogg/flac
  - thumbnail_grid      — generate a sprite-sheet PNG
  - info                — ffprobe metadata

Mirror of the REST surface; argument shapes match openapi.yaml so
generated TS/Go/Python clients can be used interchangeably with MCP.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from flickies.config import Config
from flickies.engines._license_gate import NonCommercialOptInRequired
from flickies.engines._registry import EngineNotRegistered, Registry
from flickies.fetch import fetch_to_temp
from flickies.ffmpeg import FFmpeg
from flickies.files import files_dir, resolve_safe


_log = logging.getLogger("flickies.mcp")


def build_mcp_server(
    *,
    cfg: Config,
    registry: Registry,
    ffmpeg: FFmpeg,
) -> FastMCP:
    """Construct the FastMCP server.

    Mount under `/v1/mcp` so clients hit `/v1/mcp` directly. FastMCP's
    `streamable_http_path` is set to `/` so the mount path doesn't
    double-prefix.
    """
    mcp = FastMCP(
        name="flickies",
        instructions=(
            "Self-hosted video tools: lipsync (Wav2Lip + LatentSync 1.5), "
            "face restore (GFPGAN), and pure-ffmpeg transcoding / trim / "
            "concat / scale / mux audio / extract audio / thumbnail grid / "
            "info. Input: stage via PUT /v1/files/{path} then pass file_path, "
            "OR pass file_url for server fetch. Output: every video-producing "
            "tool requires exactly one of output_path (writes under FILES_DIR; "
            "response {path,size}) xor output_url (presigned PUT; response "
            "{url,size}). Wav2Lip variants are non-commercial (LRS2); the "
            "server refuses to load them unless FLICKIES_ENABLE_NONCOMMERCIAL=1 "
            "is set in its env."
        ),
        stateless_http=True,
        json_response=True,
    )
    mcp.settings.streamable_http_path = "/"

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _resolve_video(
        file_path: str | None,
        file_url: str | None,
        *,
        suffix: str = ".mp4",
    ) -> tuple[Path, bool]:
        n = int(bool(file_path)) + int(bool(file_url))
        if n != 1:
            raise ValueError("must provide exactly one of: file_path, file_url")
        if file_path:
            return resolve_safe(files_dir(cfg.data_dir), file_path), False
        assert file_url is not None
        return await fetch_to_temp(file_url, suffix=suffix), True

    def _resolve_output(output_path: str | None) -> Path:
        if not output_path:
            raise ValueError("output_path is required for MCP tools (output_url not supported here)")
        dst = resolve_safe(files_dir(cfg.data_dir), output_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        return dst

    # ── tools ────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def list_engines() -> dict[str, Any]:
        """List configured ML engines + their load state.

        ffmpeg is NOT an engine — it's the always-on CPU backend.
        """
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
            })
        return {"engines": out, "loaded_engine": registry.loaded_slug()}

    @mcp.tool()
    async def info(
        file_path: str | None = None,
        file_url: str | None = None,
    ) -> dict[str, Any]:
        """ffprobe metadata for a video — duration, codec, fps, dimensions, bitrate."""
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            return await ffmpeg.info(src)
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass

    @mcp.tool()
    async def lipsync(
        face_path: str | None = None,
        face_url: str | None = None,
        audio_path: str | None = None,
        audio_url: str | None = None,
        engine: str = "latentsync-1.5",
        output_path: str | None = None,
        restore_face: bool = False,
    ) -> dict[str, Any]:
        """Drive a face from an audio track.

        Engines:
          - latentsync-1.5 (Apache-2.0, default on CUDA)
          - wav2lip / wav2lip-gan (LRS2 non-commercial; requires
            FLICKIES_ENABLE_NONCOMMERCIAL=1)
        """
        dst = _resolve_output(output_path)
        face, face_is_tmp = await _resolve_video(face_path, face_url, suffix=".mp4")
        audio_n = int(bool(audio_path)) + int(bool(audio_url))
        if audio_n != 1:
            raise ValueError("must provide exactly one of: audio_path, audio_url")
        audio_is_tmp = False
        if audio_url:
            audio = await fetch_to_temp(audio_url, suffix=".wav")
            audio_is_tmp = True
        else:
            assert audio_path is not None
            audio = resolve_safe(files_dir(cfg.data_dir), audio_path)
        try:
            try:
                eng = await registry.acquire(engine)
            except EngineNotRegistered as e:
                raise ValueError(f"unknown engine: {engine}") from e
            try:
                await eng.lipsync(face, audio, dst)  # type: ignore[attr-defined]
            except NonCommercialOptInRequired as e:
                raise ValueError(str(e)) from e
        finally:
            if face_is_tmp:
                try:
                    face.unlink()
                except OSError:
                    pass
            if audio_is_tmp:
                try:
                    audio.unlink()
                except OSError:
                    pass
        size = dst.stat().st_size
        # Optional face restore chain — acquires GFPGAN second; this triggers
        # hot-swap eviction of the lipsync model, which is desired (frees VRAM).
        if restore_face:
            try:
                gfp = await registry.acquire("gfpgan")
                tmp_out = dst.with_suffix(".restored.mp4")
                await gfp.restore(dst, tmp_out)  # type: ignore[attr-defined]
                tmp_out.replace(dst)
            except EngineNotRegistered:
                pass
            size = dst.stat().st_size
        return {"path": output_path, "size": size}

    @mcp.tool()
    async def restore(
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """GFPGAN face restore — clean up the face region in a video."""
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            try:
                eng = await registry.acquire("gfpgan")
            except EngineNotRegistered as e:
                raise ValueError("gfpgan engine not registered") from e
            await eng.restore(src, dst)  # type: ignore[attr-defined]
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def transcode(
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
        output_format: str = "mp4",
        video_codec: str | None = None,
        audio_codec: str | None = None,
        crf: int | None = None,
        preset: str | None = None,
        fps: float | None = None,
        gif_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Universal re-encode. output_format = mp4/webm/mov/mkv/gif.

        gif_options only consulted when output_format=gif:
          { width?, loop?, palette_mode? }
        """
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.transcode(
                src, dst,
                output_format=output_format,
                video_codec=video_codec,
                audio_codec=audio_codec,
                crf=crf, preset=preset, fps=fps,
                gif_options=gif_options,
            )
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def trim(
        file_path: str | None = None,
        file_url: str | None = None,
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        precise: bool = False,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Trim a video to [start_sec, end_sec].

        precise=False (default): stream-copy. Fast, but cuts snap to the
        nearest keyframe — start can land seconds late if start_sec falls
        mid-GOP. precise=True: re-encode for frame-accurate boundaries
        (slower; single-generation, visually transparent).
        """
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.trim(src, dst, start_sec, end_sec, precise=precise)
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def concat(
        inputs_paths: list[str] | None = None,
        inputs_urls: list[str] | None = None,
        precise: bool = False,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Concat >=2 videos in order.

        precise=False (default): concat demuxer with stream-copy. Requires
        all inputs to share codec/timebase/SAR. precise=True: re-encode
        through the concat demuxer with uniform x264 + AAC so mixed inputs
        join cleanly (slower; single-generation re-encode).
        """
        dst = _resolve_output(output_path)
        if bool(inputs_paths) == bool(inputs_urls):
            raise ValueError("exactly one of inputs_paths / inputs_urls required")
        tmps: list[Path] = []
        try:
            if inputs_urls:
                resolved = []
                for url in inputs_urls:
                    t = await fetch_to_temp(url, suffix=".mp4")
                    tmps.append(t)
                    resolved.append(t)
            else:
                assert inputs_paths is not None
                resolved = [resolve_safe(files_dir(cfg.data_dir), p) for p in inputs_paths]
            await ffmpeg.concat(resolved, dst, precise=precise)
        finally:
            for t in tmps:
                try:
                    t.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def scale(
        file_path: str | None = None,
        file_url: str | None = None,
        width: int = 0,
        height: int = 0,
        keep_aspect: bool = True,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Scale a video to width x height."""
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.scale(src, dst, width=width, height=height, keep_aspect=keep_aspect)
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def mux_audio(
        video_path_or_url: str,
        audio_path_or_url: str,
        output_path: str | None = None,
        replace_existing_audio: bool = True,
    ) -> dict[str, Any]:
        """Mux an audio track into a video (replace or merge)."""
        dst = _resolve_output(output_path)

        async def _resolve(spec: str, suffix: str) -> tuple[Path, bool]:
            if spec.startswith(("http://", "https://")):
                return await fetch_to_temp(spec, suffix=suffix), True
            return resolve_safe(files_dir(cfg.data_dir), spec), False

        v, v_tmp = await _resolve(video_path_or_url, ".mp4")
        a, a_tmp = await _resolve(audio_path_or_url, ".wav")
        try:
            await ffmpeg.mux_audio(v, a, dst, replace_existing_audio=replace_existing_audio)
        finally:
            if v_tmp:
                try:
                    v.unlink()
                except OSError:
                    pass
            if a_tmp:
                try:
                    a.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def extract_audio(
        file_path: str | None = None,
        file_url: str | None = None,
        audio_format: str = "wav",
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Extract the audio track from a video as wav/mp3/m4a/ogg/flac."""
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.extract_audio(src, dst, audio_format)
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def thumbnail_grid(
        file_path: str | None = None,
        file_url: str | None = None,
        rows: int = 3,
        cols: int = 4,
        cell_width: int = 320,
        cell_height: int = 180,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Generate a thumbnail-grid PNG (sprite sheet) from a video."""
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.thumbnail_grid(
                src, dst,
                rows=rows, cols=cols,
                cell_width=cell_width, cell_height=cell_height,
            )
        finally:
            if is_tmp:
                try:
                    src.unlink()
                except OSError:
                    pass
        return {"path": output_path, "size": dst.stat().st_size}

    return mcp
