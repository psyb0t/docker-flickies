"""Wav2Lip lipsync engine — Rudrabha/Wav2Lip.

Two variants share this class — selected via `variant` in engines.json:
  - "base" → wav2lip.pth — max sync accuracy, softer mouth
  - "gan"  → wav2lip_gan.pth — sharper mouth, slightly worse sync

Weights are non-commercial (LRS2 training data). Load gated behind
FLICKIES_ENABLE_NONCOMMERCIAL=1 via _license_gate.

Implementation: vendored model + face_detection + audio code lives at
flickies._vendor.wav2lip. Inference here mirrors the upstream
inference.py contract — face video / still + audio → output video.

Weights expected at:  FLICKIES_DATA_DIR/models/wav2lip/<weights_file>
S3FD face detector weights auto-fetched on first call to a path under
FLICKIES_DATA_DIR/models/wav2lip/s3fd-619a316812.pth.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from flickies.engines._license_gate import require_noncommercial_optin
from flickies.engines.base import Engine
from flickies.errors import CODE_BAD_REQUEST, CODE_INTERNAL, http_error


_log = logging.getLogger("flickies.engines.wav2lip")

_IMG_SIZE = 96
_MEL_STEP_SIZE = 16
_S3FD_URL = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
_S3FD_BASENAME = "s3fd-619a316812.pth"


def _data_dir() -> Path:
    return Path(os.environ.get("FLICKIES_DATA_DIR", "/data"))


def _models_dir() -> Path:
    d = _data_dir() / "models" / "wav2lip"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _select_device() -> str:
    env = os.environ.get("FLICKIES_DEVICE", "auto").lower()
    if env in ("cpu", "cuda"):
        return env
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _ensure_s3fd_weights() -> Path:
    """Download S3FD detector weights into models dir if missing."""
    dst = _models_dir() / _S3FD_BASENAME
    if dst.is_file() and dst.stat().st_size > 0:
        return dst
    import urllib.request
    _log.info("downloading S3FD weights: url=%s dst=%s", _S3FD_URL, dst)
    tmp = dst.with_suffix(".part")
    urllib.request.urlretrieve(_S3FD_URL, str(tmp))
    tmp.rename(dst)
    return dst


_WAV2LIP_WEIGHT_URLS = {
    "wav2lip.pth": "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip.pth",
    "wav2lip_gan.pth": "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth",
}


def _ensure_wav2lip_weights(weights_file: str) -> Path:
    """Return path to the checkpoint, auto-downloading from the HF mirror if absent.

    Auto-download is skipped when FLICKIES_OFFLINE=1 — operators in
    air-gapped envs put the .pth into the models dir out of band.
    """
    dst = _models_dir() / weights_file
    if dst.is_file() and dst.stat().st_size > 0:
        return dst
    offline = os.environ.get("FLICKIES_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")
    url = _WAV2LIP_WEIGHT_URLS.get(weights_file)
    if offline or url is None:
        raise http_error(
            400, CODE_BAD_REQUEST,
            f"Wav2Lip weights missing at {dst}. Download {weights_file} into "
            f"{_models_dir()} and retry. Default mirror: {url}",
            expected_path=str(dst),
        )
    import urllib.request
    _log.info("downloading wav2lip weights: url=%s dst=%s", url, dst)
    tmp = dst.with_suffix(".part")
    urllib.request.urlretrieve(url, str(tmp))
    tmp.rename(dst)
    return dst


def _load_wav2lip_model(checkpoint_path: Path, device: str):
    """Load the Wav2Lip model from a .pth checkpoint, mirror upstream loader."""
    import torch

    from flickies._vendor.wav2lip.models import Wav2Lip as Wav2LipNet

    _log.info("loading wav2lip checkpoint: path=%s device=%s", checkpoint_path, device)
    if device == "cuda":
        ckpt = torch.load(str(checkpoint_path), map_location="cuda", weights_only=False)
    else:
        ckpt = torch.load(str(checkpoint_path), map_location=torch.device("cpu"), weights_only=False)
    state = ckpt.get("state_dict", ckpt)
    new_s = {}
    for k, v in state.items():
        new_s[k.replace("module.", "")] = v
    model = Wav2LipNet()
    model.load_state_dict(new_s)
    model = model.to(device)
    return model.eval()


class Wav2Lip(Engine):
    def __init__(self, slug: str, **spec: Any) -> None:
        super().__init__(slug, **spec)
        self._model = None
        self._detector = None
        self._device: str | None = None

    def loaded(self) -> bool:
        return self._model is not None

    async def get_model(self) -> Any:
        require_noncommercial_optin(self.slug)
        if self._model is not None:
            return self._model
        # Load on a worker thread — torch.load + S3FD download are blocking.
        await asyncio.to_thread(self._load_sync)
        return self._model

    def _load_sync(self) -> None:
        device = _select_device()
        weights_file = self.spec.get("weights_file", "wav2lip.pth")
        ckpt = _ensure_wav2lip_weights(weights_file)
        s3fd_path = _ensure_s3fd_weights()
        self._device = device
        self._model = _load_wav2lip_model(ckpt, device)
        from flickies._vendor.wav2lip import face_detection
        # Patch the SFDDetector to read its weights from our managed path.
        self._detector = face_detection.FaceAlignment(
            face_detection.LandmarksType._2D,
            flip_input=False,
            device=device,
        )
        # The SFDDetector defaults to a path next to its own .py. We don't
        # control that path. Symlink our managed weight in if absent.
        from flickies._vendor.wav2lip.face_detection.detection.sfd import sfd_detector as _sfd_mod
        default_sfd_path = Path(_sfd_mod.__file__).parent / "s3fd.pth"
        if not default_sfd_path.exists():
            try:
                default_sfd_path.symlink_to(s3fd_path)
            except OSError:
                # Fall back to copy if filesystem refuses symlinks.
                import shutil
                shutil.copy2(s3fd_path, default_sfd_path)

    async def unload(self) -> None:
        if self._model is None:
            return
        try:
            import torch
            del self._model
            del self._detector
            self._model = None
            self._detector = None
            if self._device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._device = None
            _log.info("wav2lip unloaded: slug=%s", self.slug)
        except ImportError:
            pass

    async def health(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "variant": self.spec.get("variant", "base"),
            "loaded": self.loaded(),
            "device": self._device,
            "noncommercial": True,
        }

    async def lipsync(self, face: Path, audio: Path, dst: Path) -> None:
        require_noncommercial_optin(self.slug)
        await self.get_model()
        from fastapi import HTTPException
        try:
            await asyncio.to_thread(self._lipsync_sync, face, audio, dst)
        except HTTPException:
            raise  # already a structured error envelope; bubble up untouched
        except Exception as e:  # noqa: BLE001
            _log.exception("wav2lip inference failed: slug=%s", self.slug)
            raise http_error(500, CODE_INTERNAL, f"wav2lip inference failed: {e}") from e
        self._touch()

    # ── synchronous core ───────────────────────────────────────────────
    def _lipsync_sync(self, face: Path, audio: Path, dst: Path) -> None:
        """Mirror the upstream inference.py main(), simplified.

        - Read face frames (video) or single image
        - Extract audio → 16kHz wav → mel chunks
        - For each mel chunk: detect face, crop, build img+mel batches,
          run model, paste result back into the frame
        - Re-encode to mp4 with the original audio track
        """
        import cv2
        import numpy as np
        import torch
        from tqdm import tqdm

        from flickies._vendor.wav2lip import audio as wav_audio

        assert self._model is not None and self._detector is not None

        # ── load frames ────────────────────────────────────────────────
        static = face.suffix.lower() in (".jpg", ".jpeg", ".png")
        fps_in: float
        full_frames: list[Any]
        if static:
            img = cv2.imread(str(face))
            if img is None:
                raise http_error(400, CODE_BAD_REQUEST, f"could not read face image: {face}")
            full_frames = [img]
            fps_in = 25.0
        else:
            cap = cv2.VideoCapture(str(face))
            if not cap.isOpened():
                raise http_error(400, CODE_BAD_REQUEST, f"could not open face video: {face}")
            fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0
            full_frames = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                full_frames.append(frame)
            cap.release()
            if not full_frames:
                raise http_error(400, CODE_BAD_REQUEST, "face video has zero frames")

        # ── load audio + mel ───────────────────────────────────────────
        # Ensure audio is a 16kHz wav. Upstream relies on ffmpeg to convert.
        with tempfile.TemporaryDirectory(prefix="flickies-w2l-") as work_str:
            work = Path(work_str)
            wav16 = work / "audio.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(audio),
                    "-strict", "-2",
                    "-ar", "16000",
                    "-ac", "1",
                    str(wav16),
                ],
                check=True,
            )

            wav = wav_audio.load_wav(str(wav16), 16000)
            mel = wav_audio.melspectrogram(wav)
            if np.isnan(mel.reshape(-1)).sum() > 0:
                raise http_error(
                    400, CODE_BAD_REQUEST,
                    "audio mel contains NaN — try a different audio file (TTS output often triggers this)",
                )

            # ── mel chunks aligned to fps ──────────────────────────────
            mel_chunks: list[Any] = []
            mel_idx_multiplier = 80.0 / fps_in
            i = 0
            while True:
                start_idx = int(i * mel_idx_multiplier)
                if start_idx + _MEL_STEP_SIZE > mel.shape[1]:
                    mel_chunks.append(mel[:, mel.shape[1] - _MEL_STEP_SIZE:])
                    break
                mel_chunks.append(mel[:, start_idx:start_idx + _MEL_STEP_SIZE])
                i += 1

            # Truncate frames to match mel chunk count (mirrors upstream).
            full_frames = full_frames[: len(mel_chunks)]

            # ── face detection (single pass over all frames) ───────────
            faces_bb = self._detect_faces_batch(full_frames)

            # ── build batches + run model ──────────────────────────────
            batch_size = int(self.spec.get("inference_batch_size", 16))
            h, w = full_frames[0].shape[:2]
            silent_out = work / "silent.mp4"
            writer = cv2.VideoWriter(
                str(silent_out),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps_in,
                (w, h),
            )
            try:
                img_batch: list[Any] = []
                mel_batch: list[Any] = []
                frame_batch: list[Any] = []
                coord_batch: list[Any] = []
                for k in tqdm(range(len(mel_chunks)), desc="wav2lip", disable=True):
                    idx = 0 if static else k % len(full_frames)
                    frame_to_save = full_frames[idx].copy()
                    bb = faces_bb[idx if not static else 0]
                    if bb is None:
                        # No face detected → write the original frame unchanged.
                        writer.write(frame_to_save)
                        continue
                    y1, y2, x1, x2 = bb
                    face_crop = frame_to_save[y1:y2, x1:x2]
                    face_crop = cv2.resize(face_crop, (_IMG_SIZE, _IMG_SIZE))

                    img_batch.append(face_crop)
                    mel_batch.append(mel_chunks[k])
                    frame_batch.append(frame_to_save)
                    coord_batch.append((y1, y2, x1, x2))

                    if len(img_batch) < batch_size and k < len(mel_chunks) - 1:
                        continue

                    self._flush_batch(
                        writer, img_batch, mel_batch, frame_batch, coord_batch,
                    )
                    img_batch, mel_batch, frame_batch, coord_batch = [], [], [], []
            finally:
                writer.release()

            # ── mux audio + silent video into final mp4 ────────────────
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(silent_out),
                    "-i", str(audio),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-shortest",
                    str(dst),
                ],
                check=True,
            )

    # ── detection helper (cached over frames) ──────────────────────────
    def _detect_faces_batch(self, frames: list[Any]) -> list[Any]:
        import numpy as np
        from tqdm import tqdm
        pads_top, pads_bot, pads_left, pads_right = 0, 10, 0, 0
        batch_size = int(self.spec.get("face_det_batch_size", 16))
        results: list[Any] = []
        h, w = frames[0].shape[:2]
        for i in tqdm(range(0, len(frames), batch_size), desc="face-det", disable=True):
            batch = np.array(frames[i:i + batch_size])
            try:
                preds = self._detector.get_detections_for_batch(batch)
            except Exception as e:  # noqa: BLE001
                raise http_error(500, CODE_INTERNAL, f"face detection failed: {e}") from e
            for det in preds:
                if det is None:
                    results.append(None)
                    continue
                x1, y1, x2, y2 = det
                y1 = max(0, y1 - pads_top)
                y2 = min(h, y2 + pads_bot)
                x1 = max(0, x1 - pads_left)
                x2 = min(w, x2 + pads_right)
                results.append((y1, y2, x1, x2))
        return results

    # ── model forward + paste ──────────────────────────────────────────
    def _flush_batch(
        self,
        writer,
        img_batch: list[Any],
        mel_batch: list[Any],
        frame_batch: list[Any],
        coord_batch: list[Any],
    ) -> None:
        import numpy as np
        import torch
        assert self._model is not None
        assert self._device is not None

        img_np = np.asarray(img_batch)
        mel_np = np.asarray(mel_batch)
        img_masked = img_np.copy()
        img_masked[:, _IMG_SIZE // 2:] = 0
        img_in = np.concatenate((img_masked, img_np), axis=3) / 255.0

        img_t = torch.FloatTensor(np.transpose(img_in, (0, 3, 1, 2))).to(self._device)
        mel_t = torch.FloatTensor(np.transpose(mel_np[..., np.newaxis], (0, 3, 1, 2))).to(self._device)

        with torch.no_grad():
            pred = self._model(mel_t, img_t)

        pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

        import cv2
        for p, frame, (y1, y2, x1, x2) in zip(pred, frame_batch, coord_batch):
            p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))
            frame[y1:y2, x1:x2] = p
            writer.write(frame)
