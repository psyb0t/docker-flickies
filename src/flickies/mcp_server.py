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
  - subtitles, overlay  — captions and graphics
  - crop, compose       — layout and framing
  - scenes, analyze     — cut and quality reports
  - frames              — timestamped frame samples

Mirror of the REST surface; argument shapes match openapi.yaml so
generated TS/Go/Python clients can be used interchangeably with MCP.
"""

from __future__ import annotations

import contextlib
import logging
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

from flickies.config import Config
from flickies.engines._license_gate import NonCommercialOptInRequired
from flickies.engines._registry import EngineNotRegistered, Registry
from flickies.fetch import fetch_to_temp
from flickies.ffmpeg import FFmpeg
from flickies.files import files_dir, resolve_existing, resolve_safe
from flickies.video_edits import (
    Compose,
    Crop,
    GridStyle,
    Overlay,
    QualityAnalysis,
    SampleFrames,
    Scenes,
    Subtitles,
    Transition,
    Word,
)

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
            "tool requires output_path, written under FILES_DIR. Wav2Lip variants are non-commercial (LRS2); the "
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
            return resolve_existing(files_dir(cfg.data_dir), file_path), False
        assert file_url is not None
        return await fetch_to_temp(file_url, suffix=suffix), True

    def _resolve_output(output_path: str | None) -> Path:
        if not output_path:
            raise ValueError(
                "output_path is required for MCP tools (output_url not supported here)"
            )
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
            out.append(
                {
                    "slug": slug,
                    "executor": spec.get("executor", ""),
                    "variant": spec.get("variant"),
                    "loaded": eng.loaded(),
                    "noncommercial": bool(spec.get("noncommercial", False)),
                    "cuda_only": bool(spec.get("cuda_only", False)),
                    "vram_gb_min": spec.get("vram_gb_min"),
                    "description": spec.get("description", ""),
                }
            )
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
                with contextlib.suppress(OSError):
                    src.unlink()

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
                await registry.run(engine, "lipsync", face, audio, dst)
            except EngineNotRegistered as e:
                raise ValueError(f"unknown engine: {engine}") from e
            except NonCommercialOptInRequired as e:
                raise ValueError(str(e)) from e
        finally:
            if face_is_tmp:
                with contextlib.suppress(OSError):
                    face.unlink()
            if audio_is_tmp:
                with contextlib.suppress(OSError):
                    audio.unlink()
        size = dst.stat().st_size
        # Optional face restore chain — acquires GFPGAN second; this triggers
        # hot-swap eviction of the lipsync model, which is desired (frees VRAM).
        if restore_face:
            try:
                tmp_out = dst.with_suffix(".restored.mp4")
                await registry.run("gfpgan", "restore", dst, tmp_out)
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
                await registry.run("gfpgan", "restore", src, dst)
            except EngineNotRegistered as e:
                raise ValueError("gfpgan engine not registered") from e
        finally:
            if is_tmp:
                with contextlib.suppress(OSError):
                    src.unlink()
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
        max_size_bytes: int | None = None,
    ) -> dict[str, Any]:
        """Universal re-encode. output_format = mp4/webm/mov/mkv/gif.

        gif_options only consulted when output_format=gif:
          { width?, loop?, palette_mode? }
        """
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.transcode(
                src,
                dst,
                output_format=output_format,
                video_codec=video_codec,
                audio_codec=audio_codec,
                crf=crf,
                preset=preset,
                fps=fps,
                gif_options=gif_options,
                max_size_bytes=max_size_bytes,
            )
        finally:
            if is_tmp:
                with contextlib.suppress(OSError):
                    src.unlink()
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
                with contextlib.suppress(OSError):
                    src.unlink()
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def concat(
        inputs_paths: list[str] | None = None,
        inputs_urls: list[str] | None = None,
        precise: bool = False,
        output_path: str | None = None,
        transitions: list[Transition] | None = None,
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
                resolved = [resolve_existing(files_dir(cfg.data_dir), p) for p in inputs_paths]
            await ffmpeg.concat(resolved, dst, precise=precise, transitions=transitions)
        finally:
            for t in tmps:
                with contextlib.suppress(OSError):
                    t.unlink()
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
                with contextlib.suppress(OSError):
                    src.unlink()
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
                with contextlib.suppress(OSError):
                    v.unlink()
            if a_tmp:
                with contextlib.suppress(OSError):
                    a.unlink()
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
                with contextlib.suppress(OSError):
                    src.unlink()
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
        timestamps: bool = False,
        layout: Literal["tight", "review"] = "tight",
    ) -> dict[str, Any]:
        """Generate a thumbnail-grid PNG (sprite sheet) from a video."""
        style = GridStyle(timestamps=timestamps, layout=layout)
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            await ffmpeg.thumbnail_grid(
                src,
                dst,
                rows=rows,
                cols=cols,
                cell_width=cell_width,
                cell_height=cell_height,
                timestamps=style.timestamps,
                layout=style.layout,
            )
        finally:
            if is_tmp:
                with contextlib.suppress(OSError):
                    src.unlink()
        return {"path": output_path, "size": dst.stat().st_size}

    async def _edit(
        file_path: str | None,
        file_url: str | None,
        output_path: str | None,
        suffix: str,
        operation: Callable[[Path, Path], Awaitable[None]],
    ) -> dict[str, Any]:
        dst = _resolve_output(output_path)
        src, is_tmp = await _resolve_video(file_path, file_url)
        try:
            with tempfile.TemporaryDirectory(dir=dst.parent, prefix=".flickies-") as directory:
                temporary = Path(directory) / ("result" + suffix)
                await operation(src, temporary)
                temporary.replace(dst)
        except HTTPException as exc:
            detail = exc.detail.get("message") if isinstance(exc.detail, dict) else exc.detail
            raise ValueError(str(detail)) from exc
        finally:
            if is_tmp:
                with contextlib.suppress(OSError):
                    src.unlink()
        return {"path": output_path, "size": dst.stat().st_size}

    @mcp.tool()
    async def subtitles(
        subtitle_path: str | None = None,
        words: list[Word] | None = None,
        mode: Literal["burn", "embed"] = "burn",
        words_per_line: int = 4,
        font_size: int = 56,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Burn or embed captions, or render karaoke from word timestamps."""
        spec = Subtitles(
            subtitle_path=subtitle_path,
            words=words,
            mode=mode,
            words_per_line=words_per_line,
            font_size=font_size,
        )
        subtitle = (
            resolve_existing(files_dir(cfg.data_dir), spec.subtitle_path)
            if spec.subtitle_path
            else None
        )
        return await _edit(
            file_path,
            file_url,
            output_path,
            ".mp4",
            lambda src, dst: ffmpeg.subtitles(src, dst, spec, subtitle),
        )

    @mcp.tool()
    async def overlay(
        end_sec: float,
        start_sec: float = 0,
        image_path: str | None = None,
        text: str | None = None,
        x: int = 24,
        y: int = 24,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Overlay a still image or title for a time range."""
        spec = Overlay(
            image_path=image_path, text=text, start_sec=start_sec, end_sec=end_sec, x=x, y=y
        )
        image = (
            resolve_existing(files_dir(cfg.data_dir), spec.image_path) if spec.image_path else None
        )
        return await _edit(
            file_path,
            file_url,
            output_path,
            ".mp4",
            lambda src, dst: ffmpeg.overlay(src, dst, spec, image),
        )

    @mcp.tool()
    async def crop(
        width: int,
        height: int,
        mode: Literal["crop", "pad", "blur"] = "crop",
        x: int | None = None,
        y: int | None = None,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Crop a video, letterbox it, or fill the background with a blurred copy."""
        spec = Crop(width=width, height=height, mode=mode, x=x, y=y)
        return await _edit(
            file_path, file_url, output_path, ".mp4", lambda src, dst: ffmpeg.crop(src, dst, spec)
        )

    @mcp.tool()
    async def compose(
        second_path: str,
        layout: Literal["horizontal", "vertical", "pip"] = "horizontal",
        width: int = 1280,
        height: int = 720,
        audio: Literal["first", "second", "none"] = "first",
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Combine two videos side by side, stacked, or picture in picture."""
        spec = Compose(
            second_path=second_path, layout=layout, width=width, height=height, audio=audio
        )
        second = resolve_existing(files_dir(cfg.data_dir), spec.second_path)
        return await _edit(
            file_path,
            file_url,
            output_path,
            ".mp4",
            lambda src, dst: ffmpeg.compose(src, dst, second, spec),
        )

    @mcp.tool()
    async def scenes(
        threshold: float = 10,
        artifacts: Literal["none", "frames", "clips"] = "none",
        max_scenes: int = 50,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Detect cuts and write a JSON manifest or ZIP with optional frames or clips."""
        spec = Scenes(threshold=threshold, artifacts=artifacts, max_scenes=max_scenes)
        suffix = ".json" if spec.artifacts == "none" else ".zip"
        return await _edit(
            file_path, file_url, output_path, suffix, lambda src, dst: ffmpeg.scenes(src, dst, spec)
        )

    @mcp.tool()
    async def analyze(
        black_min_sec: float = 0.25,
        freeze_min_sec: float = 0.5,
        silence_min_sec: float = 0.5,
        silence_db: float = -40,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Report black, frozen, and silent intervals as JSON."""
        spec = QualityAnalysis(
            black_min_sec=black_min_sec,
            freeze_min_sec=freeze_min_sec,
            silence_min_sec=silence_min_sec,
            silence_db=silence_db,
        )
        return await _edit(
            file_path,
            file_url,
            output_path,
            ".json",
            lambda src, dst: ffmpeg.analyze(src, dst, spec),
        )

    @mcp.tool()
    async def frames(
        sample_interval_sec: float = 1,
        max_frames: int = 60,
        file_path: str | None = None,
        file_url: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Extract timestamped JPEG samples and a frames.json manifest into a ZIP."""
        spec = SampleFrames(sample_interval_sec=sample_interval_sec, max_frames=max_frames)
        return await _edit(
            file_path, file_url, output_path, ".zip", lambda src, dst: ffmpeg.frames(src, dst, spec)
        )

    return mcp
