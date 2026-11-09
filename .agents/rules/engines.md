# Engine and image rules

Prefix: ENG.

Covers the ML engines in `src/flickies/engines/`, `engines.json`, weight downloads, the vendored model code and the image dependencies.

## Registry and executors

- **ENG1:** `engines.json` maps a slug to an `executor`; `_EXECUTOR_MAP` in `src/flickies/server.py` maps the executor to its class, and an unknown executor is skipped with a warning. Every entry has `executor` and `description` (`test_engines_json_parses` in `tests/test_smoke.py`), and Wav2Lip entries keep `noncommercial: true`.
- **ENG2:** An engine subclasses `Engine` (`src/flickies/engines/base.py`): `loaded()`, `async get_model()` that loads once in `asyncio.to_thread`, `async unload()`, `health()`, and `_touch()` after each inference so the idle sweeper sees it. The capability method is `lipsync(face, audio, dst)` or `restore(src, dst)`.
- **ENG3:** `unload()` drops every reference to the model graph first, then calls `gc.collect()`, then `torch.cuda.empty_cache()`, in that order. Without the collect, reference cycles keep the weights resident (v0.3.1).
- **ENG4:** Each executor's weight download is a module-level `_ensure_*` function, and `_prefetch_one()` in `src/flickies/prefetch.py` dispatches to it. A new executor adds its branch there.

## Weights and licenses

- **ENG5:** Weights come from `huggingface_hub.snapshot_download` of the full repository into `HF_HOME=/data/hf`, with `local_files_only` when `FLICKIES_OFFLINE` is set. A non-empty file under `/data/models/<engine>/` wins (the manual offline path). Repository ids are module constants (`_WAV2LIP_HF_REPO`, `_S3FD_HF_REPO`, `_GFPGAN_HF_REPO`, `_LATENTSYNC_HF_REPO`); weights are never committed or copied into an image.
- **ENG6:** A non-commercial engine calls `require_noncommercial_optin(self.slug)` (`src/flickies/engines/_license_gate.py`) in both `get_model()` and its capability method, as `Wav2Lip` does. The `noncommercial` flag in `engines.json` only informs `/v1/engines` and the prefetch; it does not enforce anything.

## Dependencies and images

- **ENG7:** Light runtime dependencies change only through `make pkg-add`, `pkg-remove`, `pkg-update` or `pkg-upgrade`, which move `exclude-newer` in `pyproject.toml` first; never hand-edit `uv.lock`. The ML stack changes by editing `scripts/heavy-deps-cpu.in` or `scripts/heavy-deps-cuda.in` and running `make pkg-compile-heavy`; never hand-edit `requirements-heavy-*.txt`.
- **ENG8:** CUDA-only libraries go only in `scripts/heavy-deps-cuda.in`, and the engine that needs them is `cuda_only: true` in `engines.json`. Base images and the uv image are pinned by tag (`python:3.12-slim-bookworm`, `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`, `ghcr.io/astral-sh/uv:0.11.15`).
- **ENG9:** Keep the basicsr `functional_tensor` patch in `Dockerfile`, `Dockerfile.cuda` and `entrypoint.sh` in step; the build step runs an import check so a broken patch fails the build.
