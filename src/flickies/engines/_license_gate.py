"""Non-commercial license opt-in gate.

Mirrors audiolla's `_require_noncommercial_optin` — engines whose weights
or training data are non-commercial (LRS2-trained Wav2Lip variants) refuse
to load unless the operator sets FLICKIES_ENABLE_NONCOMMERCIAL=1 in the
server env.
"""
from __future__ import annotations

import os


class NonCommercialOptInRequired(RuntimeError):
    pass


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def require_noncommercial_optin(engine_slug: str) -> None:
    raw = os.environ.get("FLICKIES_ENABLE_NONCOMMERCIAL", "").strip().lower()
    if raw in _TRUTHY:
        return
    raise NonCommercialOptInRequired(
        f"{engine_slug}: non-commercial opt-in missing. "
        f"Set FLICKIES_ENABLE_NONCOMMERCIAL=1 in the server environment "
        f"to load this engine. The model is trained on non-commercial "
        f"data (LRS2) and may not be used in commercial deployments."
    )


def noncommercial_enabled() -> bool:
    return os.environ.get("FLICKIES_ENABLE_NONCOMMERCIAL", "").strip().lower() in _TRUTHY
