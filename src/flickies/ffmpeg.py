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
import contextlib
import json
import logging
import re
import shlex
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flickies.errors import CODE_BAD_REQUEST, CODE_FFMPEG_FAILED, http_error
from flickies.video_edits import (
    Compose,
    Crop,
    Overlay,
    QualityAnalysis,
    SampleFrames,
    Scenes,
    Subtitles,
    Transition,
    karaoke_ass,
)

_log = logging.getLogger("flickies.ffmpeg")


async def _run(*args: str, capture_stdout: bool = False) -> tuple[bytes, bytes]:
    """Run ffmpeg/ffprobe; raise 500 ffmpeg_failed on non-zero exit.

    Single choke point for every ffmpeg/ffprobe invocation — DEBUG here
    captures the full command (inputs, output path, all flags) + the
    completion, so every op is reconstructable from the logs without each
    method re-logging its own args.
    """
    cmd = shlex.join(args)
    _log.debug("ffmpeg exec", extra={"tool": args[0], "cmd": cmd})
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE if capture_stdout else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await proc.communicate()
    except asyncio.CancelledError:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
        raise
    if proc.returncode != 0:
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
    _log.debug(
        "ffmpeg ok",
        extra={"tool": args[0], "rc": 0, "stdout_bytes": len(out or b"")},
    )
    return out, err


# Precise re-encode params shared by trim(precise=True) and concat(precise=True).
# H.264 CRF 18 + AAC 192k = visually transparent single-generation re-encode.
_PRECISE_VIDEO_CODEC = "libx264"
_PRECISE_CRF = "18"
_PRECISE_PRESET = "veryfast"
_PRECISE_AUDIO_CODEC = "aac"
_PRECISE_AUDIO_BITRATE = "192k"
_FFMPEG = (
    "ffmpeg",
    "-y",
    "-nostdin",
    "-hide_banner",
    "-loglevel",
    "error",
    "-filter_complex_threads",
    "1",
    "-filter_threads",
    "1",
)
_MP4 = (
    "-c:v",
    _PRECISE_VIDEO_CODEC,
    "-preset",
    _PRECISE_PRESET,
    "-crf",
    _PRECISE_CRF,
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    _PRECISE_AUDIO_CODEC,
    "-movflags",
    "+faststart",
)
_SAFE_VIDEO = (
    "-protocol_whitelist",
    "file,pipe",
    "-format_whitelist",
    "mov,matroska,webm,avi,mpegts,mpeg,mpegvideo,flv,ogg,gif,asf,ivf",
)
_MAX_SUBTITLE_BYTES = 4 * 1024 * 1024


class FFmpeg:
    """Plain helper. NOT an Engine. Wrap ffmpeg + ffprobe as async methods."""

    async def version(self) -> str:
        out, _ = await _run("ffmpeg", "-version", capture_stdout=True)
        return out.decode("utf-8", errors="replace").splitlines()[0]

    # ── trim ───────────────────────────────────────────────────────────
    async def trim(
        self,
        src: Path,
        dst: Path,
        start: float,
        end: float,
        *,
        precise: bool = False,
    ) -> None:
        # Default (precise=False) uses `-c copy` for speed but can only cut on
        # keyframe boundaries — ffmpeg snaps `start` to the nearest keyframe,
        # potentially eating up to one GOP of leading content (~8s at 30fps
        # with a 250-frame GOP). Set precise=True to force a frame-accurate
        # single-generation re-encode (slower; visually transparent at CRF 18).
        if end <= start:
            raise http_error(400, "BAD_REQUEST", "end_sec must be > start_sec")
        _log.debug(
            "trim start",
            extra={
                "src": str(src),
                "dst": str(dst),
                "start_sec": start,
                "end_sec": end,
                "reason": "precise_reencode" if precise else "stream_copy",
            },
        )
        if precise:
            await _run(
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(src),
                "-ss",
                str(start),
                "-to",
                str(end),
                "-c:v",
                _PRECISE_VIDEO_CODEC,
                "-crf",
                _PRECISE_CRF,
                "-preset",
                _PRECISE_PRESET,
                "-c:a",
                _PRECISE_AUDIO_CODEC,
                "-b:a",
                _PRECISE_AUDIO_BITRATE,
                str(dst),
            )
            return
        await _run(
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            str(src),
            "-c",
            "copy",
            str(dst),
        )

    # ── concat ─────────────────────────────────────────────────────────
    async def concat(
        self,
        inputs: list[Path],
        dst: Path,
        *,
        precise: bool = False,
        transitions: list[Transition] | None = None,
    ) -> None:
        if transitions is not None:
            await self._transition_concat(inputs, dst, transitions)
            return
        # Default uses the concat demuxer with `-c copy` — fast but requires
        # all inputs to share identical codec / timebase / SAR params. When
        # they don't (e.g. mixing sources from different encoders), the result
        # corrupts or fails. Set precise=True to re-encode through the concat
        # demuxer with uniform x264 + AAC params so any inputs concat cleanly.
        if len(inputs) < 2:
            raise http_error(400, "BAD_REQUEST", "concat needs >= 2 inputs")
        _log.debug(
            "concat start",
            extra={
                "inputs": [str(p) for p in inputs],
                "dst": str(dst),
                "n_inputs": len(inputs),
                "reason": "precise_reencode" if precise else "stream_copy",
            },
        )
        listing = "\n".join(f"file '{p.resolve()}'" for p in inputs) + "\n"
        list_file = dst.parent / f".{dst.name}.concat.txt"
        list_file.parent.mkdir(parents=True, exist_ok=True)
        list_file.write_text(listing)
        try:
            if precise:
                await _run(
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-c:v",
                    _PRECISE_VIDEO_CODEC,
                    "-crf",
                    _PRECISE_CRF,
                    "-preset",
                    _PRECISE_PRESET,
                    "-c:a",
                    _PRECISE_AUDIO_CODEC,
                    "-b:a",
                    _PRECISE_AUDIO_BITRATE,
                    str(dst),
                )
            else:
                await _run(
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-c",
                    "copy",
                    str(dst),
                )
        finally:
            with contextlib.suppress(OSError):
                list_file.unlink()

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
        max_size_bytes: int | None = None,
    ) -> None:
        if max_size_bytes is not None:
            if (
                type(max_size_bytes) is not int
                or max_size_bytes < 64 * 1024
                or output_format != "mp4"
                or video_codec not in {None, "libx264"}
                or audio_codec not in {None, "aac"}
                or crf is not None
            ):
                raise http_error(
                    400,
                    CODE_BAD_REQUEST,
                    "file-size targeting requires MP4, H.264/AAC, at least 65536 bytes and no CRF",
                )
            await self._transcode_to_size(src, dst, max_size_bytes, fps=fps, preset=preset)
            return
        is_gif = output_format.lower() == "gif"
        _log.debug(
            "transcode start",
            extra={
                "src": str(src),
                "dst": str(dst),
                "output_format": output_format,
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "crf": crf,
                "preset": preset,
                "fps": fps,
                "reason": "gif_palette_two_pass" if is_gif else "standard_reencode",
            },
        )
        if is_gif:
            await self._transcode_gif(src, dst, fps=fps, gif_options=gif_options or {})
            return
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
        ]
        cmd += ["-c:v", video_codec] if video_codec else []
        cmd += ["-c:a", audio_codec] if audio_codec else []
        cmd += ["-crf", str(crf)] if crf is not None else []
        cmd += ["-preset", preset] if preset else []
        cmd += ["-r", str(fps)] if fps is not None else []
        cmd += [str(dst)]
        await _run(*cmd)

    async def _transcode_to_size(
        self, src: Path, dst: Path, limit: int, *, fps: float | None, preset: str | None
    ) -> None:
        meta = await self.info(src, restricted=True)
        duration = float(meta["duration_sec"])
        if duration <= 0 or not meta["video_codec"]:
            raise http_error(
                400, CODE_BAD_REQUEST, "file-size targeting requires a video with known duration"
            )
        if fps is not None and (type(fps) not in {int, float} or not 1 <= fps <= 240):
            raise http_error(400, CODE_BAD_REQUEST, "fps must be between 1 and 240")
        if preset is not None and preset not in {
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        }:
            raise http_error(400, CODE_BAD_REQUEST, "unsupported H.264 preset")
        audio_bitrate = 64000 if meta["audio_codec"] else 0
        bitrate = int((limit - min(limit // 10, 32768)) * 8 / duration) - audio_bitrate
        common = [
            *_FFMPEG,
            *_SAFE_VIDEO,
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-c:v",
            _PRECISE_VIDEO_CODEC,
            "-preset",
            preset or _PRECISE_PRESET,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        ]
        if fps is not None:
            common.extend(("-r", str(fps)))
        with tempfile.TemporaryDirectory(prefix="flickies-pass-") as directory:
            for attempt in range(3):
                if bitrate < 10000:
                    break
                log = str(Path(directory) / str(attempt))
                args = [*common, "-b:v", str(bitrate), "-passlogfile", log]
                await _run(*args, "-pass", "1", "-an", "-f", "null", "-")
                await _run(
                    *args,
                    "-pass",
                    "2",
                    "-map",
                    "0:a:0?",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "64k",
                    "-movflags",
                    "+faststart",
                    str(dst),
                )
                size = dst.stat().st_size
                if size <= limit:
                    return
                bitrate = int(bitrate * limit / size * 0.85)
        raise http_error(400, CODE_BAD_REQUEST, "could not encode within max_size_bytes")

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
        vf = f"{scale}fps={gif_fps}," f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        await _run(
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-filter_complex",
            vf,
            "-loop",
            str(loop),
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
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vf",
            vf,
            "-c:a",
            "copy",
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
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0" if replace_existing_audio else "1:a:0",
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
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
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
        timestamps: bool = False,
        layout: str = "tight",
    ) -> None:
        if timestamps or layout != "tight":
            if (
                not 1 <= rows * cols <= 100
                or not 16 <= cell_width <= 1920
                or not 16 <= cell_height <= 1080
            ):
                raise http_error(400, CODE_BAD_REQUEST, "review grid dimensions exceed limits")
            if rows <= 0 or cols <= 0 or rows * cols * cell_width * cell_height > 32_000_000:
                raise http_error(400, CODE_BAD_REQUEST, "review grid canvas exceeds limits")
            meta = await self.info(src, restricted=True)
            duration = float(meta["duration_sec"])
            if duration <= 0:
                raise http_error(
                    400, CODE_BAD_REQUEST, "review grid requires a video with known duration"
                )
            rate = rows * cols / duration
            layers = [
                f"setpts=PTS-STARTPTS,fps={rate}:start_time=0,scale={cell_width}:{cell_height}"
            ]
            if timestamps:
                layers.append(
                    r"drawtext=font=DejaVu Sans:text='%{pts\:hms}':x=8:y=h-th-8:fontcolor=white:fontsize=16:box=1:boxcolor=black@0.7"
                )
            margin = 8 if layout == "review" else 0
            layers.append(f"tile={cols}x{rows}:margin={margin}:padding={margin}:color=black")
            await _run(
                *_FFMPEG,
                *_SAFE_VIDEO,
                "-i",
                str(src),
                "-vf",
                ",".join(layers),
                "-frames:v",
                "1",
                str(dst),
            )
            return
        # Pick `rows*cols` evenly-spaced frames, tile them.
        n = rows * cols
        # Use `select='not(mod(n,N))'` with N derived from total frames via
        # a probe; simpler — use the `thumbnail` filter then tile.
        vf = f"thumbnail=100,scale={cell_width}:{cell_height}," f"tile={cols}x{rows}"
        await _run(
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vf",
            vf,
            "-frames:v",
            "1",
            "-vsync",
            "vfr",
            str(dst),
        )
        # n is only used in vf-build above; reference it to satisfy linters.
        _ = n

    async def subtitles(self, src: Path, dst: Path, spec: Subtitles, subtitle: Path | None) -> None:
        with tempfile.TemporaryDirectory(prefix="flickies-captions-") as directory:
            if subtitle is None:
                staged = Path(directory) / "captions.ass"
                staged.write_text(
                    karaoke_ass(spec.words or [], spec.words_per_line, spec.font_size),
                    encoding="utf-8",
                )
            else:
                suffix = subtitle.suffix.lower()
                if suffix not in {".srt", ".ass"} or subtitle.stat().st_size > _MAX_SUBTITLE_BYTES:
                    raise http_error(
                        400, CODE_BAD_REQUEST, "use an SRT or ASS subtitle up to 4 MiB"
                    )
                staged = Path(directory) / f"captions{suffix}"
                shutil.copyfile(subtitle, staged)
            if spec.mode == "embed":
                await _run(
                    *_FFMPEG,
                    *_SAFE_VIDEO,
                    "-i",
                    str(src),
                    "-f",
                    staged.suffix[1:],
                    "-i",
                    str(staged),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-map",
                    "1:s:0",
                    *_MP4,
                    "-c:s",
                    "mov_text",
                    str(dst),
                )
                return
            await _run(
                *_FFMPEG,
                *_SAFE_VIDEO,
                "-i",
                str(src),
                "-vf",
                f"subtitles={staged}",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                *_MP4,
                str(dst),
            )

    async def overlay(self, src: Path, dst: Path, spec: Overlay, image: Path | None) -> None:
        with tempfile.TemporaryDirectory(prefix="flickies-overlay-") as directory:
            if image is None:
                image = Path(directory) / "title.png"
                magick = shutil.which("magick") or "convert"
                text = (spec.text or "").replace("\\", "\\\\").replace("%", "%%")
                await _run(
                    magick,
                    "-limit",
                    "memory",
                    "64MiB",
                    "-limit",
                    "map",
                    "128MiB",
                    "-limit",
                    "disk",
                    "0",
                    "-background",
                    "#000000B0",
                    "-fill",
                    "white",
                    "-font",
                    "DejaVu-Sans",
                    "-pointsize",
                    "32",
                    f"label:{text}",
                    "-bordercolor",
                    "#000000B0",
                    "-border",
                    "14x10",
                    str(image),
                )
            elif image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise http_error(400, CODE_BAD_REQUEST, "overlay image must be PNG, JPEG or WebP")
            graph = (
                f"[0:v][1:v]overlay=x={spec.x}:y={spec.y}:"
                f"enable='gte(t,{spec.start_sec})*lt(t,{spec.end_sec})'[video]"
            )
            await _run(
                *_FFMPEG,
                *_SAFE_VIDEO,
                "-i",
                str(src),
                "-protocol_whitelist",
                "file",
                "-f",
                "image2",
                "-pattern_type",
                "none",
                "-i",
                str(image),
                "-filter_complex",
                graph,
                "-map",
                "[video]",
                "-map",
                "0:a:0?",
                *_MP4,
                str(dst),
            )

    async def crop(self, src: Path, dst: Path, spec: Crop) -> None:
        width, height = spec.width, spec.height
        size = f"{width}:{height}"
        fit = f"scale={size}:force_original_aspect_ratio=decrease:force_divisible_by=2"
        fill = f"scale={size}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={size}"
        if spec.x is not None and spec.y is not None:
            meta = await self.info(src, restricted=True)
            if spec.x + width > meta["width"] or spec.y + height > meta["height"]:
                raise http_error(400, CODE_BAD_REQUEST, "crop rectangle exceeds source dimensions")
            graph = f"[0:v]crop={size}:{spec.x}:{spec.y}:exact=1,setsar=1[video]"
        elif spec.mode == "pad":
            graph = f"[0:v]{fit},pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1[video]"
        elif spec.mode == "blur":
            graph = f"[0:v]split[back][front];[back]{fill},boxblur=3[bg];[front]{fit}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[video]"
        else:
            graph = f"[0:v]{fill},setsar=1[video]"
        await _run(
            *_FFMPEG,
            *_SAFE_VIDEO,
            "-i",
            str(src),
            "-filter_complex",
            graph,
            "-map",
            "[video]",
            "-map",
            "0:a:0?",
            *_MP4,
            str(dst),
        )

    async def compose(self, src: Path, dst: Path, second: Path, spec: Compose) -> None:
        width, height = spec.width, spec.height
        if spec.layout == "horizontal":
            sizes = ((width // 2, height), (width // 2, height))
            combine = "hstack=shortest=1"
        elif spec.layout == "vertical":
            sizes = ((width, height // 2), (width, height // 2))
            combine = "vstack=shortest=1"
        else:
            sizes = ((width, height), (width // 4, height // 4))
            combine = "overlay=W-w-8:H-h-8:shortest=1"
        graph = [
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{i}]"
            for i, (w, h) in enumerate(sizes)
        ]
        graph.append(f"[v0][v1]{combine}[video]")
        duration = min(
            (await self.info(src, restricted=True))["duration_sec"],
            (await self.info(second, restricted=True))["duration_sec"],
        )
        if duration <= 0:
            raise http_error(
                400, CODE_BAD_REQUEST, "composition requires two videos with known duration"
            )
        audio_args = [] if spec.audio == "none" else ["-map", f"{int(spec.audio == 'second')}:a:0?"]
        await _run(
            *_FFMPEG,
            *_SAFE_VIDEO,
            "-i",
            str(src),
            *_SAFE_VIDEO,
            "-i",
            str(second),
            "-filter_complex",
            ";".join(graph),
            "-map",
            "[video]",
            *audio_args,
            "-t",
            str(duration),
            *_MP4,
            str(dst),
        )

    async def _transition_concat(
        self, inputs: list[Path], dst: Path, joins: list[Transition]
    ) -> None:
        if not 2 <= len(inputs) <= 16 or len(joins) != len(inputs) - 1:
            raise http_error(
                400, CODE_BAD_REQUEST, "provide one transition per join across 2 to 16 inputs"
            )
        info = [await self.info(src, restricted=True) for src in inputs]
        width = int(info[0]["width"]) // 2 * 2
        height = int(info[0]["height"]) // 2 * 2
        rate = min(60.0, max(1.0, float(info[0]["fps"]) or 30.0))
        durations = [int(float(item["duration_sec"]) * rate) / rate for item in info]
        if not width or not height or any(d <= 0 for d in durations):
            raise http_error(
                400, CODE_BAD_REQUEST, "transitions require video inputs with known duration"
            )
        overlaps = [round(join.duration_sec * rate) / rate for join in joins]
        for index, duration in enumerate(durations):
            before = overlaps[index - 1] if index else 0
            after = overlaps[index] if index < len(overlaps) else 0
            if before + after >= duration:
                raise http_error(
                    400, CODE_BAD_REQUEST, "transitions must leave frames between overlaps"
                )
        if any(
            join.effect != "cut" and not overlap
            for join, overlap in zip(joins, overlaps, strict=True)
        ):
            raise http_error(400, CODE_BAD_REQUEST, "transition duration is shorter than one frame")
        graph: list[str] = []
        cmd: list[str] = []
        has_audio = any(item["audio_codec"] for item in info)
        for index, src in enumerate(inputs):
            duration = durations[index]
            cmd.extend((*_SAFE_VIDEO, "-i", str(src)))
            graph.append(
                f"[{index}:v]fps={rate},scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv444p,trim=duration={duration},settb=1/1000000,setpts=PTS-STARTPTS[v{index}]"
            )
            if has_audio:
                audio = (
                    f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,apad"
                    if info[index]["audio_codec"]
                    else "anullsrc=r=48000:cl=stereo"
                )
                graph.append(f"{audio},atrim=duration={duration},asetpts=PTS-STARTPTS[a{index}]")
        video, audio = "[v0]", "[a0]"
        elapsed = durations[0]
        for index, join in enumerate(joins, start=1):
            overlap = overlaps[index - 1]
            if join.effect == "cut":
                graph.append(f"{video}[v{index}]concat=n=2:v=1:a=0,settb=1/1000000[vj{index}]")
                if has_audio:
                    graph.append(f"{audio}[a{index}]concat=n=2:v=0:a=1[aj{index}]")
            else:
                graph.append(
                    f"{video}[v{index}]xfade=transition={join.effect}:duration={overlap}:offset={elapsed - overlap}[vj{index}]"
                )
                if has_audio:
                    graph.append(f"{audio}[a{index}]acrossfade=d={overlap}[aj{index}]")
            video, audio = f"[vj{index}]", f"[aj{index}]"
            elapsed += durations[index] - overlap
        await _run(
            *_FFMPEG,
            *cmd,
            "-filter_complex",
            ";".join(graph),
            "-map",
            video,
            *(["-map", audio] if has_audio else []),
            *_MP4,
            str(dst),
        )

    async def scenes(self, src: Path, dst: Path, spec: Scenes) -> None:
        meta = await self.info(src, restricted=True)
        duration: float = meta["duration_sec"]
        if duration <= 0 or not meta["video_codec"]:
            raise http_error(
                400, CODE_BAD_REQUEST, "scene detection requires a video with known duration"
            )
        out, _ = await _run(
            *_FFMPEG,
            *_SAFE_VIDEO,
            "-i",
            str(src),
            "-an",
            "-vf",
            f"setpts=PTS-STARTPTS,scdet=t={spec.threshold}:s=1,metadata=print:file=-",
            "-frames:v",
            str(spec.max_scenes),
            "-f",
            "null",
            "-",
            capture_stdout=True,
        )
        score = 0.0
        cuts: list[tuple[float, float]] = [(0.0, 0.0)]
        for line in out.decode().splitlines():
            if line.startswith("lavfi.scd.score="):
                score = float(line.partition("=")[2])
            elif line.startswith("lavfi.scd.time="):
                timestamp = float(line.partition("=")[2])
                if cuts[-1][0] < timestamp < duration:
                    cuts.append((timestamp, score))
        shots = [
            {
                "start_sec": start,
                "end_sec": cuts[index + 1][0] if index + 1 < len(cuts) else duration,
                "score": cut_score,
            }
            for index, (start, cut_score) in enumerate(cuts[: spec.max_scenes])
        ]
        if len(cuts) > spec.max_scenes:
            raise http_error(
                400,
                CODE_BAD_REQUEST,
                "more scenes than max_scenes; raise the limit or detection threshold",
            )
        manifest = json.dumps({"scenes": shots})
        if spec.artifacts == "none":
            dst.write_text(manifest, encoding="utf-8")
            return
        with (
            tempfile.TemporaryDirectory(prefix="flickies-scenes-") as directory,
            zipfile.ZipFile(dst, "w") as archive,
        ):
            archive.writestr("scenes.json", manifest)
            for index, shot in enumerate(shots, start=1):
                ext = "jpg" if spec.artifacts == "frames" else "mp4"
                artifact = Path(directory) / f"scene-{index:03d}.{ext}"
                if spec.artifacts == "frames":
                    await _run(
                        *_FFMPEG,
                        "-ss",
                        str(shot["start_sec"]),
                        *_SAFE_VIDEO,
                        "-i",
                        str(src),
                        "-frames:v",
                        "1",
                        str(artifact),
                    )
                else:
                    await self.trim(src, artifact, shot["start_sec"], shot["end_sec"], precise=True)
                archive.write(artifact, artifact.name)
                artifact.unlink()

    async def analyze(self, src: Path, dst: Path, spec: QualityAnalysis) -> None:
        meta = await self.info(src, restricted=True)
        duration = float(meta["duration_sec"])
        if duration <= 0 or not meta["video_codec"]:
            raise http_error(
                400, CODE_BAD_REQUEST, "quality analysis requires a video with known duration"
            )
        args = [
            *_FFMPEG,
            "-loglevel",
            "info",
            *_SAFE_VIDEO,
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-vf",
            f"setpts=PTS-STARTPTS,blackdetect=d={spec.black_min_sec},freezedetect=d={spec.freeze_min_sec}",
        ]
        if meta["audio_codec"]:
            args.extend(
                (
                    "-map",
                    "0:a:0",
                    "-af",
                    f"asetpts=PTS-STARTPTS,silencedetect=n={spec.silence_db}dB:d={spec.silence_min_sec}",
                )
            )
        _, stderr = await _run(*args, "-f", "null", "-")
        events: list[dict[str, Any]] = []
        starts: dict[str, float] = {}
        minimums = {
            "black": spec.black_min_sec,
            "freeze": spec.freeze_min_sec,
            "silence": spec.silence_min_sec,
        }
        for kind, boundary, value in re.findall(
            r"\b(black|freeze|silence)_(start|end):\s*([0-9.eE+-]+)",
            stderr.decode(errors="replace"),
        ):
            timestamp = float(value)
            if boundary == "start":
                starts[kind] = timestamp
            elif kind in starts:
                start = starts.pop(kind)
                if timestamp - start >= minimums[kind] - 1e-6:
                    events.append({"kind": kind, "start_sec": start, "end_sec": timestamp})
        for kind, start in starts.items():
            if duration - start >= minimums[kind]:
                events.append({"kind": kind, "start_sec": start, "end_sec": duration})
        dst.write_text(
            json.dumps(
                {
                    "duration_sec": duration,
                    "events": sorted(events, key=lambda event: event["start_sec"]),
                }
            ),
            encoding="utf-8",
        )

    async def frames(self, src: Path, dst: Path, spec: SampleFrames) -> None:
        with tempfile.TemporaryDirectory(prefix="flickies-frames-") as directory:
            frames = await self.sample_frames(
                src, Path(directory), spec.sample_interval_sec, spec.max_frames
            )
            with zipfile.ZipFile(dst, "w") as archive:
                archive.writestr(
                    "frames.json",
                    json.dumps(
                        {"frames": [{"file": path.name, "time_sec": time} for path, time in frames]}
                    ),
                )
                for path, _ in frames:
                    archive.write(path, path.name)

    async def sample_frames(
        self, src: Path, directory: Path, interval: float, limit: int
    ) -> list[tuple[Path, float]]:
        _, stderr = await _run(
            *_FFMPEG,
            "-loglevel",
            "info",
            *_SAFE_VIDEO,
            "-i",
            str(src),
            "-an",
            "-vf",
            f"setpts=PTS-STARTPTS,select='isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})',scale=640:640:force_original_aspect_ratio=decrease,showinfo",
            "-vsync",
            "vfr",
            "-frames:v",
            str(limit),
            str(directory / "%04d.jpg"),
        )
        times = re.findall(r"pts_time:([0-9.eE+-]+)", stderr.decode(errors="replace"))
        paths = sorted(directory.glob("*.jpg"))
        if not paths or len(times) < len(paths):
            raise http_error(400, CODE_BAD_REQUEST, "no timestamped video frames to analyze")
        return [(path, float(times[i])) for i, path in enumerate(paths)]

    # ── ffprobe (info) ─────────────────────────────────────────────────
    async def info(self, src: Path, *, restricted: bool = False) -> dict[str, Any]:
        out, _ = await _run(
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            *(_SAFE_VIDEO if restricted else ()),
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
