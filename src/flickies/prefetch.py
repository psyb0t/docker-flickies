"""Boot-time weight prefetch.

Called from entrypoint.sh BEFORE uvicorn starts. Reads which engines the
operator wants warm + pulls their weights into the HF cache (proper
blob/snapshot layout, reusable across containers).

Behaviour:
  - FLICKIES_ENABLED_ENGINES unset OR empty → no prefetch (download on first
    request, same as before).
  - FLICKIES_ENABLED_ENGINES="wav2lip,latentsync-1.5" → prefetch ONLY those.
  - FLICKIES_PREFETCH_ALL=1 → prefetch every engine in engines.json (CUDA
    engines included only if FLICKIES_DEVICE=cuda OR torch.cuda.is_available()).
  - FLICKIES_OFFLINE=1 → skip prefetch (huggingface_hub will fail anyway).

idempotent: every download path is huggingface_hub's hash-verified blob
cache, so re-running is a fast etag check.

Exit code 0 even on partial failure — boot should continue and downloads
will retry lazily on first request. Failures are logged at WARNING.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path


_log = logging.getLogger("flickies.prefetch")


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _is_set(env: str) -> bool:
    return os.environ.get(env, "").strip().lower() in _TRUTHY


def _engines_file() -> Path:
    return Path(os.environ.get("FLICKIES_ENGINES_FILE", "/app/engines.json"))


def _wants_cuda() -> bool:
    env = os.environ.get("FLICKIES_DEVICE", "auto").lower()
    if env == "cuda":
        return True
    if env == "cpu":
        return False
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _selected_slugs() -> list[str]:
    raw = os.environ.get("FLICKIES_ENABLED_ENGINES", "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    if _is_set("FLICKIES_PREFETCH_ALL"):
        try:
            engines = json.loads(_engines_file().read_text()).get("engines", {})
        except OSError:
            return []
        cuda_ok = _wants_cuda()
        return [
            slug for slug, spec in engines.items()
            if cuda_ok or not bool(spec.get("cuda_only", False))
        ]
    return []


def _prefetch_one(slug: str, spec: dict) -> bool:
    """Dispatch to the engine's prefetch path. Return True on success."""
    executor = spec.get("executor")
    try:
        if executor == "wav2lip":
            from flickies.engines.wav2lip import (
                _ensure_s3fd_weights,
                _ensure_wav2lip_weights,
            )
            weights_file = spec.get("weights_file", "wav2lip.pth")
            _ensure_wav2lip_weights(weights_file)
            _ensure_s3fd_weights()
        elif executor == "latentsync":
            from flickies.engines.latentsync import _ensure_weights
            _ensure_weights()
        elif executor == "gfpgan":
            from flickies.engines.gfpgan import _ensure_gfpgan_weights
            _ensure_gfpgan_weights()
        else:
            _log.info("prefetch skip: no weights", extra={"engine_slug": slug, "executor": str(executor)})
            return True
    except Exception as e:  # noqa: BLE001
        _log.warning("prefetch failed", extra={"engine_slug": slug, "err": str(e), "reason": "download_error"})
        return False
    return True


def main() -> int:
    from flickies.logging_config import configure_logging, with_scope
    configure_logging()
    # Tag every prefetch log line with component=prefetch.
    with_scope(component="prefetch")

    if _is_set("FLICKIES_OFFLINE"):
        _log.info("prefetch skip: FLICKIES_OFFLINE=1 set", extra={"reason": "offline_mode"})
        return 0

    slugs = _selected_slugs()
    if not slugs:
        _log.info("prefetch skip: no engines selected", extra={"reason": "no_selection"})
        return 0

    try:
        engines = json.loads(_engines_file().read_text()).get("engines", {})
    except OSError as e:
        _log.warning("prefetch: cannot read engines file", extra={"err": str(e), "reason": "engines_file_unreadable"})
        return 0

    cuda_ok = _wants_cuda()
    total = ok = 0
    for slug in slugs:
        spec = engines.get(slug)
        if spec is None:
            _log.warning("prefetch: unknown engine slug", extra={"engine_slug": slug, "reason": "unknown_slug"})
            continue
        if bool(spec.get("cuda_only", False)) and not cuda_ok:
            _log.info("prefetch skip: cuda_only without CUDA", extra={"engine_slug": slug, "reason": "no_cuda"})
            continue
        if bool(spec.get("noncommercial", False)) and not _is_set("FLICKIES_ENABLE_NONCOMMERCIAL"):
            _log.info(
                "prefetch skip: noncommercial gate not opted in",
                extra={"engine_slug": slug, "reason": "noncommercial_gate"},
            )
            continue
        total += 1
        _log.info("prefetch start", extra={"engine_slug": slug, "executor": str(spec.get("executor"))})
        if _prefetch_one(slug, spec):
            ok += 1

    _log.info("prefetch done", extra={"ok": ok, "total": total})
    return 0


if __name__ == "__main__":
    sys.exit(main())
