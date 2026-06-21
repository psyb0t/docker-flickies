"""GFPGAN v1.4 face restore (TencentARC/GFPGAN, Apache-2.0).

Used as the optional post-pass after Wav2Lip to clean up the soft 96x96
mouth crop. Standalone via POST /v1/video/restore.

Implementation: shells out via the gfpgan package. Loads weights from
FLICKIES_DATA_DIR/models/gfpgan/GFPGANv1.4.pth; auto-downloads from the
official release URL on first call.

Process pattern: read frames via cv2, run restorer per frame, write back
to mp4 via cv2.VideoWriter. Audio track is preserved by muxing the
original audio over the restored frames at the end (ffmpeg pass).
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from flickies.engines.base import Engine
from flickies.errors import CODE_BAD_REQUEST, CODE_INTERNAL, http_error


_log = logging.getLogger("flickies.engines.gfpgan")


# HF mirror: leonelhs/gfpgan repo, file GFPGANv1.4.pth. Proper blob/snapshot
# cache layout — reusable across containers via HF_HOME.
_GFPGAN_HF_REPO = "leonelhs/gfpgan"
_GFPGAN_HF_FILE = "GFPGANv1.4.pth"


def _data_dir() -> Path:
    return Path(os.environ.get("FLICKIES_DATA_DIR", "/data"))


def _models_dir() -> Path:
    # Legacy flat-stage dir for FLICKIES_OFFLINE workflows.
    d = _data_dir() / "models" / "gfpgan"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _offline() -> bool:
    return os.environ.get("FLICKIES_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def _select_device() -> str:
    env = os.environ.get("FLICKIES_DEVICE", "auto").lower()
    if env in ("cpu", "cuda"):
        return env
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _ensure_gfpgan_weights() -> Path:
    """Return path to GFPGANv1.4.pth inside the leonelhs/gfpgan HF snapshot.

    Pulls the FULL repo (no allow_patterns) — blob store mirrors upstream
    so any HF-aware tool sees the same blobs. The repo includes other
    GFPGAN versions + RestoreFormer + CodeFormer (~1.5 GB total); flickies
    uses just v1.4.
    """
    legacy = _models_dir() / _GFPGAN_HF_FILE
    if legacy.is_file() and legacy.stat().st_size > 0:
        return legacy
    from huggingface_hub import snapshot_download
    _log.info("fetching gfpgan via HF snapshot", extra={"repo": _GFPGAN_HF_REPO})
    try:
        snap = Path(snapshot_download(
            repo_id=_GFPGAN_HF_REPO,
            local_files_only=_offline(),
        ))
    except Exception as e:  # noqa: BLE001
        raise http_error(
            400, CODE_BAD_REQUEST,
            f"GFPGAN repo {_GFPGAN_HF_REPO} unavailable: {e}. Manual fallback: "
            f"place {_GFPGAN_HF_FILE} at {legacy} and retry (FLICKIES_OFFLINE=1).",
        ) from e
    return snap / _GFPGAN_HF_FILE


class GFPGAN(Engine):
    def __init__(self, slug: str, **spec: Any) -> None:
        super().__init__(slug, **spec)
        self._restorer = None
        self._device: str | None = None

    def loaded(self) -> bool:
        return self._restorer is not None

    async def get_model(self) -> Any:
        if self._restorer is not None:
            return self._restorer
        await asyncio.to_thread(self._load_sync)
        return self._restorer

    def _load_sync(self) -> None:
        device = _select_device()
        ckpt = _ensure_gfpgan_weights()
        from gfpgan import GFPGANer
        _log.info("loading gfpgan", extra={"path": str(ckpt), "device": device, "engine_slug": "gfpgan"})
        # arch='clean' is the GFPGANv1.4 architecture.
        self._restorer = GFPGANer(
            model_path=str(ckpt),
            upscale=1,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=None,
            device=device,
        )
        self._device = device

    async def unload(self) -> None:
        if self._restorer is None:
            return
        try:
            import torch
            del self._restorer
            self._restorer = None
            if self._device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._device = None
            _log.info("gfpgan unloaded", extra={"engine_slug": self.slug})
        except ImportError:
            pass

    async def health(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "loaded": self.loaded(),
            "device": self._device,
            "noncommercial": False,
        }

    async def restore(self, src: Path, dst: Path) -> None:
        await self.get_model()
        from fastapi import HTTPException
        try:
            await asyncio.to_thread(self._restore_sync, src, dst)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            _log.exception("gfpgan restore failed", extra={"engine_slug": self.slug})
            raise http_error(500, CODE_INTERNAL, f"gfpgan restore failed: {e}") from e
        self._touch()

    def _restore_sync(self, src: Path, dst: Path) -> None:
        """Frame-by-frame restore. Preserves the source audio track."""
        import cv2

        assert self._restorer is not None

        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            raise http_error(400, CODE_BAD_REQUEST, f"could not open video: {src}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        with tempfile.TemporaryDirectory(prefix="flickies-gfp-") as work_str:
            work = Path(work_str)
            silent_out = work / "silent.mp4"
            writer = cv2.VideoWriter(
                str(silent_out),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (w, h),
            )
            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    try:
                        # enhance returns (cropped_faces, restored_faces, restored_img)
                        _cf, _rf, restored = self._restorer.enhance(
                            frame,
                            has_aligned=False,
                            only_center_face=False,
                            paste_back=True,
                        )
                    except Exception:  # noqa: BLE001
                        # No face detected on this frame → write original.
                        restored = frame
                    if restored is None:
                        restored = frame
                    if restored.shape[:2] != (h, w):
                        restored = cv2.resize(restored, (w, h))
                    writer.write(restored)
            finally:
                writer.release()
                cap.release()

            # Mux original audio back in.
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(silent_out),
                    "-i", str(src),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0?",
                    "-shortest",
                    str(dst),
                ],
                check=True,
            )
