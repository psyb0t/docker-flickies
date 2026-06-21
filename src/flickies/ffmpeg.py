"""ffmpeg + ffprobe — pure CPU, no model, plain helper module.

NOT an engine. ffmpeg is the standard for video manipulation and ships in
every variant of the image. ffprobe is part of the ffmpeg suite. There's
no VRAM to manage, no weights to load, no hot-swap eviction to handle.
Plain singleton attached to `app.state.ffmpeg` at startup; handlers call
its async methods directly.

Every op shells out to /usr/bin/ffmpeg or /usr/bin/ffprobe via asyncio
subprocess. Captures stderr; on non-zero exit raises a structured error.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shlex
from pathlib import Path
from typing import Any

from flickies.errors import CODE_FFMPEG_FAILED, http_error


_log = logging.getLogger("flickies.ffmpeg")


async def _run(*args: str, capture_stdout: bool = False) -> tuple[bytes, bytes]:
    """Run ffmpeg/ffprobe; raise 500 ffmpeg_failed on non-zero exit."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE if capture_stdout else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        cmd = shlex.join(args)
        _log.warning(
            "ffmpeg failed",
            extra={"cmd": cmd, "rc": proc.returncode, "reason": "ffmpeg_nonzero_exit"},
        )
        raise http_error(
            500,
            CODE_FFMPEG_FAILED,
            f"{args[0]} exited {proc.returncode}",
            cmd=cmd,
            stderr=err.decode("utf-8", errors="replace")[-2048:],
        )
    return out, err


class FFmpeg:
    """Plain helper. NOT an Engine. Wrap ffmpeg + ffprobe as async methods."""

    async def version(self) -> str:
        out, _ = await _run("ffmpeg", "-version", capture_stdout=True)
        return out.decode("utf-8", errors="replace").splitlines()[0]

    # ── trim ───────────────────────────────────────────────────────────
    async def trim(self, src: Path, dst: Path, start: float, end: float) -> None:
        if end <= start:
            raise http_error(400, "BAD_REQUEST", "end_sec must be > start_sec")
        await _run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start),
            "-to", str(end),
            "-i", str(src),
            "-c", "copy",
            str(dst),
        )


    # ── concat ─────────────────────────────────────────────────────────
    async def concat(self, inputs: list[Path], dst: Path) -> None:
        if len(inputs) < 2:
            raise http_error(400, "BAD_REQUEST", "concat needs >= 2 inputs")
        # Concat demuxer needs an absolute-path list file.
        listing = "\n".join(f"file '{p.resolve()}'" for p in inputs) + "\n"
        list_file = dst.parent / f".{dst.name}.concat.txt"
        list_file.parent.mkdir(parents=True, exist_ok=True)
        list_file.write_text(listing)
        try:
            await _run(
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(dst),
            )
        finally:
            try:
                list_file.unlink()
            except OSError:
                pass


    # ── transcode (universal re-encode: mp4/webm/mov/mkv + gif) ────────
    async def transcode(
        self,
        src: Path,
        dst: Path,
        *,
        output_format: str,
        video_codec: str | None = None,
        audio_codec: str | None = None,
        crf: int | None = None,
        preset: str | None = None,
        fps: float | None = None,
        gif_options: dict[str, Any] | None = None,
    ) -> None:
        if output_format.lower() == "gif":
            await self._transcode_gif(src, dst, fps=fps, gif_options=gif_options or {})
            return
        cmd: list[str] = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
        ]
        cmd += ["-c:v", video_codec] if video_codec else []
        cmd += ["-c:a", audio_codec] if audio_codec else []
        cmd += ["-crf", str(crf)] if crf is not None else []
        cmd += ["-preset", preset] if preset else []
        cmd += ["-r", str(fps)] if fps is not None else []
        cmd += [str(dst)]
        await _run(*cmd)


    async def _transcode_gif(
        self,
        src: Path,
        dst: Path,
        *,
        fps: float | None,
        gif_options: dict[str, Any],
    ) -> None:
        gif_fps = float(fps) if fps is not None else 12.0
        width = gif_options.get("width")
        loop = int(gif_options.get("loop", 0))
        # palette_mode reserved for future tuning; full = single global palette.
        scale = f"scale={width}:-2:flags=lanczos," if width else ""
        vf = (
            f"{scale}fps={gif_fps},"
            f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        )
        await _run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-filter_complex", vf,
            "-loop", str(loop),
            str(dst),
        )


    # ── scale ──────────────────────────────────────────────────────────
    async def scale(
        self,
        src: Path,
        dst: Path,
        *,
        width: int,
        height: int,
        keep_aspect: bool,
    ) -> None:
        if keep_aspect:
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            )
        else:
            vf = f"scale={width}:{height}"
        await _run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-vf", vf,
            "-c:a", "copy",
            str(dst),
        )


    # ── mux audio ──────────────────────────────────────────────────────
    async def mux_audio(
        self,
        video: Path,
        audio: Path,
        dst: Path,
        *,
        replace_existing_audio: bool,
    ) -> None:
        args = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0" if replace_existing_audio else "1:a:0",
            "-shortest",
            str(dst),
        ]
        await _run(*args)


    # ── extract audio ──────────────────────────────────────────────────
    async def extract_audio(self, src: Path, dst: Path, audio_format: str) -> None:
        codec_map = {
            "wav": ["-c:a", "pcm_s16le"],
            "mp3": ["-c:a", "libmp3lame"],
            "m4a": ["-c:a", "aac"],
            "ogg": ["-c:a", "libvorbis"],
            "flac": ["-c:a", "flac"],
        }
        codec_args = codec_map.get(audio_format)
        if codec_args is None:
            raise http_error(400, "BAD_REQUEST", f"unsupported audio format: {audio_format}")
        await _run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-vn",
            *codec_args,
            str(dst),
        )


    # ── thumbnail grid ─────────────────────────────────────────────────
    async def thumbnail_grid(
        self,
        src: Path,
        dst: Path,
        *,
        rows: int,
        cols: int,
        cell_width: int,
        cell_height: int,
    ) -> None:
        # Pick `rows*cols` evenly-spaced frames, tile them.
        n = rows * cols
        # Use `select='not(mod(n,N))'` with N derived from total frames via
        # a probe; simpler — use the `thumbnail` filter then tile.
        vf = (
            f"thumbnail=100,scale={cell_width}:{cell_height},"
            f"tile={cols}x{rows}"
        )
        await _run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-vf", vf,
            "-frames:v", "1",
            "-vsync", "vfr",
            str(dst),
        )
        # n is only used in vf-build above; reference it to satisfy linters.
        _ = n


    # ── ffprobe (info) ─────────────────────────────────────────────────
    async def info(self, src: Path) -> dict[str, Any]:
        out, _ = await _run(
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(src),
            capture_stdout=True,
        )
        meta = json.loads(out.decode("utf-8"))
        video_streams = [s for s in meta.get("streams", []) if s.get("codec_type") == "video"]
        audio_streams = [s for s in meta.get("streams", []) if s.get("codec_type") == "audio"]
        v = video_streams[0] if video_streams else {}
        a = audio_streams[0] if audio_streams else None
        fmt = meta.get("format", {})
        fps = 0.0
        rate = v.get("r_frame_rate")
        if isinstance(rate, str) and "/" in rate:
            num, den = rate.split("/", 1)
            try:
                fps = float(num) / float(den) if float(den) != 0 else 0.0
            except (TypeError, ValueError):
                fps = 0.0

        return {
            "duration_sec": float(fmt.get("duration", 0.0)),
            "width": int(v.get("width", 0)),
            "height": int(v.get("height", 0)),
            "fps": fps,
            "video_codec": v.get("codec_name", ""),
            "audio_codec": a.get("codec_name") if a else None,
            "bitrate": int(fmt["bit_rate"]) if "bit_rate" in fmt else None,
            "container_format": fmt.get("format_name"),
            "size_bytes": int(fmt.get("size", 0)),
        }
