# syntax=docker/dockerfile:1.7
#
# CPU image — python:3.12-slim + ffmpeg + torch CPU + Wav2Lip (+ S3FD) + GFPGAN-CPU.
# Heavy CUDA-only engines (LatentSync 1.5) live in Dockerfile.cuda.
# Wav2Lip CPU is feasible for short clips (~1-3 fps with face-detection bottleneck).
#
# Supply chain:
#   1. Lightweight runtime deps (fastapi/uvicorn/pydantic/httpx/mcp) via
#      `uv sync --frozen --no-dev --no-editable` against uv.lock — uv verifies
#      sdist/wheel hashes from the lockfile.
#   2. Heavy ML deps (torch/cv2/librosa/...) via `uv pip install --require-hashes`
#      against requirements-heavy-cpu.txt — compiled by scripts/compile_heavy_deps.sh.

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:${PATH} \
    HF_HOME=/data/hf

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv

WORKDIR /app

# 1) Light deps from uv.lock — hash-verified, reproducible.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# 2) Heavy stack — torch CPU + cv2 + librosa + numpy + numba + scipy + soundfile + tqdm.
#    Versions pinned in requirements-heavy-cpu.txt (compiled by
#    scripts/compile_heavy_deps.sh). Most lines also carry --hash; a small number
#    of torch-transitive deps (jinja2/filelock/fsspec/...) don't have hashes
#    captured under the current pytorch-wheel-index + uv combo. TODO: enable
#    `--require-hashes` once that resolves. The exclude-newer date gate in
#    pyproject.toml + the version pins are the supply-chain backstop today.
COPY requirements-heavy-cpu.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-config \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        --index-strategy unsafe-best-match \
        -r requirements-heavy-cpu.txt

# basicsr (GFPGAN's dep) does `from torchvision.transforms.functional_tensor
# import rgb_to_grayscale` — the `functional_tensor` module was removed in
# torchvision 0.17. Community-standard patch: rewrite the import.
RUN sed -i 's|from torchvision.transforms.functional_tensor import rgb_to_grayscale|from torchvision.transforms.functional import rgb_to_grayscale|' \
        /opt/venv/lib/python3.12/site-packages/basicsr/data/degradations.py \
    && python -c "from basicsr.data import degradations; print('basicsr import OK')"

COPY engines.json /app/engines.json
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /data

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
