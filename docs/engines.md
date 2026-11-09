---
title: "Engines"
description: "The flickies ML engines (LatentSync 1.5, Wav2Lip, Wav2Lip-GAN, GFPGAN v1.4): licenses, the non-commercial gate, VRAM, hot-swap eviction and engines.json."
nav_order: 6
---

# Engines

An engine is a machine-learning model flickies loads into memory: the lipsync models and GFPGAN. ffmpeg is not an engine. It is always available, needs no weights and never competes for the GPU.

| Slug | What it does | License | Image | Min VRAM |
| --- | --- | --- | --- | --- |
| `latentsync-1.5` | Lipsync in Stable Diffusion 1.5 latent space (ByteDance). Default lipsync engine. Slower than Wav2Lip. | Apache-2.0 | CUDA only | 8 GB |
| `wav2lip` | Wav2Lip base (Rudrabha): best sync, soft 96x96 mouth crop. | non-commercial | CPU and CUDA | 3 GB |
| `wav2lip-gan` | Wav2Lip with the GAN refiner: sharper mouth, slightly worse sync. | non-commercial | CPU and CUDA | 3 GB |
| `gfpgan` | GFPGAN v1.4 face restore (TencentARC), frame by frame. | Apache-2.0 | CPU and CUDA | 2 GB |

The VRAM figures are the `vram_gb_min` values in [engines.json](https://github.com/psyb0t/docker-flickies/blob/main/engines.json). On the tested RTX 3060 12 GB, LatentSync 1.5 takes about 8 GB and a Wav2Lip then GFPGAN chain peaks around 5 GB.

## Picking a lipsync engine

- Commercial use, or no reason to choose otherwise: `latentsync-1.5` on the CUDA image. No opt-in needed.
- CPU only, short clips, non-commercial use: `wav2lip` with `FLICKIES_ENABLE_NONCOMMERCIAL=1`. A 3-second clip takes around 44 seconds on the CPU.
- Wav2Lip output looks soft around the mouth: run [restore](api.md#post-v1videorestore) on it, or use `wav2lip-gan`.

## Licenses

Wav2Lip and Wav2Lip-GAN are trained on LRS2, which is licensed for non-commercial use only, and the vendored Wav2Lip source under [src/flickies/_vendor/wav2lip/](https://github.com/psyb0t/docker-flickies/tree/main/src/flickies/_vendor/wav2lip) is limited to personal, research and non-commercial use by its authors. The server refuses to load either Wav2Lip engine unless `FLICKIES_ENABLE_NONCOMMERCIAL=1` is set in its environment: lipsync with them answers 403 `NONCOMMERCIAL_GATE_REFUSED`, the boot prefetch skips them, and the entrypoint prints the gate state at startup. A caller cannot flip it per request. The source code itself ships in every image either way.

| Engine | License | Gate |
| --- | --- | --- |
| LatentSync 1.5 | Apache-2.0 | none |
| Wav2Lip, Wav2Lip-GAN | LRS2 non-commercial | `FLICKIES_ENABLE_NONCOMMERCIAL=1` |
| GFPGAN | Apache-2.0 | none |
| ffmpeg, ffprobe (not an engine) | LGPL | none |

flickies itself is WTFPL. [THIRD_PARTY.md](https://github.com/psyb0t/docker-flickies/blob/main/THIRD_PARTY.md) lists the vendored code and its licenses.

## One engine at a time

All engines share one memory pool, and only one is loaded at a time:

1. The first request for an engine loads it, downloading its weights first if they are not in `/data/hf` ([Deployment](deployment.md#model-weights)).
2. A request for a different engine unloads the current one, then loads the new one. Loads are serialised, so two requests for different engines cannot load both at once.
3. A background sweep every `FLICKIES_SWEEP_INTERVAL_SECS` (30 s) unloads an engine that has been idle for `FLICKIES_IDLE_UNLOAD_SECS` (600 s).
4. `DELETE /v1/engines/{slug}` unloads one on demand.

Alternating between engines, for example lipsync then restore on every clip, reloads a model each time. If you need two engines warm at once, run two containers.

## Device selection

`FLICKIES_DEVICE` decides where Wav2Lip and GFPGAN run: `auto` (CUDA if torch sees a GPU), `cpu` or `cuda`. LatentSync 1.5 checks for CUDA itself and refuses with 400 `latentsync-1.5 is CUDA-only; FLICKIES_DEVICE=cuda required.` when there is none. On GPUs with compute capability 8 or higher it runs in float16, otherwise float32.

LatentSync's libraries (diffusers, transformers, mediapipe and the rest) are only installed in the CUDA image. On the CPU image a LatentSync request fails at load with a plain-text 500, which is also what you get when you leave `engine` out on the CPU image, since `latentsync-1.5` is the default.

## The engine registry

The registry is [engines.json](https://github.com/psyb0t/docker-flickies/blob/main/engines.json), read from `FLICKIES_ENGINES_FILE` (default `/app/engines.json`). Each key is a slug:

```json
{
  "engines": {
    "wav2lip-gan": {
      "executor": "wav2lip",
      "variant": "gan",
      "weights_file": "wav2lip_gan.pth",
      "weights_size_mb": 436,
      "cuda_only": false,
      "noncommercial": true,
      "vram_gb_min": 3,
      "description": "Wav2Lip + GAN refiner ..."
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `executor` | `wav2lip`, `latentsync` or `gfpgan`. An entry with any other value is skipped with a warning. |
| `variant` | Free text, shown in `/v1/engines`. |
| `weights_file` | Wav2Lip: which checkpoint in the `Nekochu/Wav2Lip` repository to load. |
| `weights_size_mb` | Informational. |
| `cuda_only` | Shown in `/v1/engines`; the boot prefetch skips the engine without a GPU. |
| `noncommercial` | Shown in `/v1/engines`; the boot prefetch skips the engine without the opt-in. The gate itself is enforced by the Wav2Lip executor, not by this flag. |
| `vram_gb_min` | Informational. |
| `description` | Shown in `/v1/engines`. |
| `inference_steps`, `guidance_scale` | LatentSync only. Default `20` and `1.5`. |

The Hugging Face repositories are fixed in the executors; the registry cannot point an engine at a different repository.
