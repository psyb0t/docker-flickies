#!/bin/sh
# flickies entrypoint — execs the FastAPI server. Heavy model prefetch
# (Wav2Lip, LatentSync 1.5, GFPGAN) fires only for slugs listed in
# FLICKIES_ENABLED_ENGINES so a CPU image doesn't pull GB of CUDA-only weights.
set -eu

: "${FLICKIES_HOST:=0.0.0.0}"
: "${FLICKIES_PORT:=8000}"
: "${FLICKIES_DEVICE:=auto}"
: "${FLICKIES_ENGINES_FILE:=/app/engines.json}"
: "${FLICKIES_DATA_DIR:=/data}"
: "${FLICKIES_ENABLED_ENGINES:=}"
: "${FLICKIES_ENABLE_NONCOMMERCIAL:=}"
: "${FLICKIES_LOG_LEVEL:=INFO}"
: "${FLICKIES_LOG_FILE:=${FLICKIES_DATA_DIR}/logs/flickies.log}"
: "${FLICKIES_AUTH_TOKEN:=}"

# torch weights cache → persistent volume.
: "${TORCH_HOME:=${FLICKIES_DATA_DIR}/torch_cache}"

# HF token aliasing — same pattern as audiolla/talkies.
if [ -n "${HUGGINGFACE_TOKEN:-}" ] && [ -z "${HF_TOKEN:-}" ]; then
    HF_TOKEN="${HUGGINGFACE_TOKEN}"
    export HF_TOKEN
fi
if [ -n "${HF_TOKEN:-}" ] && [ -z "${HUGGINGFACE_TOKEN:-}" ]; then
    HUGGINGFACE_TOKEN="${HF_TOKEN}"
    export HUGGINGFACE_TOKEN
fi

export FLICKIES_HOST FLICKIES_PORT FLICKIES_DEVICE
export FLICKIES_ENGINES_FILE FLICKIES_DATA_DIR FLICKIES_ENABLED_ENGINES
export FLICKIES_ENABLE_NONCOMMERCIAL TORCH_HOME
export FLICKIES_LOG_LEVEL FLICKIES_LOG_FILE FLICKIES_AUTH_TOKEN

mkdir -p "${FLICKIES_DATA_DIR}/models" "${FLICKIES_DATA_DIR}/uploads" "${TORCH_HOME}" "$(dirname "${FLICKIES_LOG_FILE}")"

# Auth posture announcement.
if [ -n "${FLICKIES_AUTH_TOKEN}" ]; then
    echo "[flickies] bearer auth enabled (FLICKIES_AUTH_TOKEN set)" >&2
else
    echo "[flickies] bearer auth DISABLED (FLICKIES_AUTH_TOKEN unset)" >&2
fi

# basicsr (GFPGAN dep) does `from torchvision.transforms.functional_tensor
# import rgb_to_grayscale` — the `functional_tensor` module was removed in
# torchvision 0.17 (moved into `functional`). Community-standard patch:
# rewrite the offending import on first boot.
BASICSR_DEGRADATIONS="$(python -c "import basicsr, os; print(os.path.join(os.path.dirname(basicsr.__file__), 'data', 'degradations.py'))" 2>/dev/null || echo "")"
if [ -n "${BASICSR_DEGRADATIONS}" ] && [ -f "${BASICSR_DEGRADATIONS}" ]; then
    if grep -q "torchvision.transforms.functional_tensor" "${BASICSR_DEGRADATIONS}" 2>/dev/null; then
        sed -i 's|from torchvision.transforms.functional_tensor import rgb_to_grayscale|from torchvision.transforms.functional import rgb_to_grayscale|' "${BASICSR_DEGRADATIONS}" || true
        echo "[flickies] patched basicsr functional_tensor import" >&2
    fi
fi

# Announce license posture in the boot log so operators see it immediately.
case "$(printf '%s' "${FLICKIES_ENABLE_NONCOMMERCIAL}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on)
        echo "[flickies] FLICKIES_ENABLE_NONCOMMERCIAL=1 — Wav2Lip variants will load." >&2
        ;;
    *)
        echo "[flickies] FLICKIES_ENABLE_NONCOMMERCIAL not set — Wav2Lip variants refuse to load. LatentSync 1.5 is the commercial-safe default." >&2
        ;;
esac

# Prefetch model weights for any engines listed in FLICKIES_ENABLED_ENGINES
# (or all of them when FLICKIES_PREFETCH_ALL=1). Idempotent — huggingface_hub
# hash-verifies cached blobs. Boot continues regardless of prefetch outcome.
# Set FLICKIES_OFFLINE=1 to skip + stage weights manually.
python -m flickies.prefetch || echo "[flickies] prefetch returned non-zero; boot continues, weights will fetch lazily" >&2

exec python -m flickies
