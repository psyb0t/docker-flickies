"""LatentSync 1.5 (bytedance/LatentSync, Apache-2.0).

Pinned to v1.5 — fits ~8 GB VRAM on RTX 3060 12 GB. v1.6 (18 GB VRAM)
is out of scope until the hardware ceiling rises.

Architecture: SD-1.5 backbone (`stabilityai/sd-vae-ft-mse` VAE) +
Whisper-tiny audio embeds → cross-attn into UNet3D via AnimateDiff.
Async-only (seconds-to-tens-of-seconds per clip on consumer GPU).

Apache-2.0, no non-commercial gate. Default engine when
FLICKIES_ENABLE_NONCOMMERCIAL is not set on a CUDA-equipped host.

Weight bundle download: the upstream "model.tar" at
https://weights.replicate.delivery/default/chunyu-li/LatentSync/model.tar
contains all checkpoints (UNet + Whisper + VAE auxiliary + face aux).
Extracted into FLICKIES_DATA_DIR/models/latentsync/.

Implementation: vendored code at flickies._vendor.latentsync_pkg.
We construct the LipsyncPipeline directly and call it; the upstream
inference script's behaviour is preserved.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from flickies.engines.base import Engine
from flickies.errors import CODE_BAD_REQUEST, CODE_INTERNAL, http_error


_log = logging.getLogger("flickies.engines.latentsync")


_MODEL_TAR_URL = "https://weights.replicate.delivery/default/chunyu-li/LatentSync/model.tar"


def _data_dir() -> Path:
    return Path(os.environ.get("FLICKIES_DATA_DIR", "/data"))


def _models_dir() -> Path:
    d = _data_dir() / "models" / "latentsync"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_weights() -> Path:
    """Download + extract model.tar into models dir if absent.

    The tar contains a full `checkpoints/` tree — we materialise it under
    models/latentsync/ and use that as the working dir.
    """
    root = _models_dir()
    ckpt = root / "latentsync_unet.pt"
    if ckpt.is_file():
        return root
    offline = os.environ.get("FLICKIES_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")
    if offline:
        raise http_error(
            400, CODE_BAD_REQUEST,
            f"LatentSync weights missing at {ckpt}. Download {_MODEL_TAR_URL} "
            f"and extract into {root} (offline mode).",
        )
    tar_dst = root / "model.tar"
    _log.info("downloading LatentSync model.tar: url=%s dst=%s", _MODEL_TAR_URL, tar_dst)
    tmp = tar_dst.with_suffix(".part")
    urllib.request.urlretrieve(_MODEL_TAR_URL, str(tmp))
    tmp.rename(tar_dst)
    _log.info("extracting LatentSync model.tar")
    subprocess.run(
        ["tar", "-xf", str(tar_dst), "-C", str(root), "--strip-components=1"],
        check=True,
    )
    try:
        tar_dst.unlink()
    except OSError:
        pass
    return root


def _config_path() -> Path:
    # Use the vendored stage2.yaml (256x256 resolution, fits 3060 12GB).
    from flickies._vendor.latentsync_pkg import __file__ as pkg_init
    return Path(pkg_init).parent / "configs" / "unet" / "stage2.yaml"


class LatentSync(Engine):
    def __init__(self, slug: str, **spec: Any) -> None:
        super().__init__(slug, **spec)
        self._pipeline = None
        self._device: str | None = None
        self._dtype = None
        self._config = None

    def loaded(self) -> bool:
        return self._pipeline is not None

    async def get_model(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        await asyncio.to_thread(self._load_sync)
        return self._pipeline

    def _load_sync(self) -> None:
        import torch
        from diffusers import AutoencoderKL, DDIMScheduler
        from omegaconf import OmegaConf

        from flickies._vendor.latentsync_pkg.models.unet import UNet3DConditionModel
        from flickies._vendor.latentsync_pkg.pipelines.lipsync_pipeline import LipsyncPipeline
        from flickies._vendor.latentsync_pkg.whisper.audio2feature import Audio2Feature

        if not torch.cuda.is_available():
            raise http_error(
                400, CODE_BAD_REQUEST,
                "latentsync-1.5 is CUDA-only; FLICKIES_DEVICE=cuda required.",
            )

        weights_root = _ensure_weights()
        config = OmegaConf.load(_config_path())
        self._config = config
        is_fp16 = torch.cuda.get_device_capability()[0] > 7
        self._dtype = torch.float16 if is_fp16 else torch.float32

        # Scheduler config ships in the vendored configs dir as a JSON.
        scheduler_dir = _config_path().parent.parent  # configs/
        scheduler = DDIMScheduler.from_pretrained(str(scheduler_dir))

        # Whisper checkpoint
        if config.model.cross_attention_dim == 768:
            whisper_path = weights_root / "whisper" / "small.pt"
        elif config.model.cross_attention_dim == 384:
            whisper_path = weights_root / "whisper" / "tiny.pt"
        else:
            raise http_error(500, CODE_INTERNAL, "unsupported cross_attention_dim")

        audio_encoder = Audio2Feature(
            model_path=str(whisper_path),
            device="cuda",
            num_frames=config.data.num_frames,
            audio_feat_length=config.data.audio_feat_length,
        )

        vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=self._dtype)
        vae.config.scaling_factor = 0.18215
        vae.config.shift_factor = 0

        unet, _ = UNet3DConditionModel.from_pretrained(
            OmegaConf.to_container(config.model),
            str(weights_root / "latentsync_unet.pt"),
            device="cpu",
        )
        unet = unet.to(dtype=self._dtype)

        pipeline = LipsyncPipeline(
            vae=vae,
            audio_encoder=audio_encoder,
            unet=unet,
            scheduler=scheduler,
        ).to("cuda")

        self._pipeline = pipeline
        self._device = "cuda"
        _log.info("latentsync loaded: device=%s dtype=%s", self._device, self._dtype)

    async def unload(self) -> None:
        if self._pipeline is None:
            return
        try:
            import torch
            del self._pipeline
            self._pipeline = None
            self._device = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            _log.info("latentsync unloaded: slug=%s", self.slug)
        except ImportError:
            pass

    async def health(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "variant": self.spec.get("variant", "1.5"),
            "loaded": self.loaded(),
            "device": self._device,
            "noncommercial": False,
        }

    async def lipsync(self, face: Path, audio: Path, dst: Path) -> None:
        await self.get_model()
        from fastapi import HTTPException
        try:
            await asyncio.to_thread(self._lipsync_sync, face, audio, dst)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            _log.exception("latentsync inference failed: slug=%s", self.slug)
            raise http_error(500, CODE_INTERNAL, f"latentsync inference failed: {e}") from e
        self._touch()

    def _lipsync_sync(self, face: Path, audio: Path, dst: Path) -> None:
        import torch
        from accelerate.utils import set_seed
        assert self._pipeline is not None and self._config is not None

        seed = int.from_bytes(os.urandom(2), "big")
        set_seed(seed)

        with tempfile.TemporaryDirectory(prefix="flickies-ls-") as work_str:
            work = Path(work_str)
            # Resolve mask_image_path against the vendored utils dir
            # (config carries an upstream-relative `latentsync/utils/mask.png`).
            from flickies._vendor.latentsync_pkg import __file__ as _pkg_init
            mask_abs = Path(_pkg_init).parent / "utils" / "mask.png"
            self._pipeline(
                video_path=str(face),
                audio_path=str(audio),
                video_out_path=str(dst),
                num_frames=self._config.data.num_frames,
                num_inference_steps=int(self.spec.get("inference_steps", 20)),
                guidance_scale=float(self.spec.get("guidance_scale", 1.5)),
                weight_dtype=self._dtype,
                width=self._config.data.resolution,
                height=self._config.data.resolution,
                mask_image_path=str(mask_abs),
                temp_dir=str(work),
            )
