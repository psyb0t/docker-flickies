"""Sentinel errors + error envelope helper. Matches the OpenAPI ErrorBody shape.

Error codes are UPPER_SNAKE_CASE. The same code names appear in:
  - openapi.yaml under ErrorBody.code.examples
  - this module as module-level constants
  - generated Go + Python clients (so callers can switch on code without
    duplicating string literals)
"""
from __future__ import annotations

from fastapi import HTTPException


# ── codes ──────────────────────────────────────────────────────────────────
CODE_BAD_REQUEST = "BAD_REQUEST"
CODE_UNAUTHORIZED = "UNAUTHORIZED"
CODE_NOT_FOUND = "NOT_FOUND"
CODE_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
CODE_VALIDATION_FAILED = "VALIDATION_FAILED"
CODE_INTERNAL = "INTERNAL_SERVER_ERROR"
CODE_NONCOMMERCIAL_GATE_REFUSED = "NONCOMMERCIAL_GATE_REFUSED"
CODE_ENGINE_NOT_REGISTERED = "ENGINE_NOT_REGISTERED"
CODE_FFMPEG_FAILED = "FFMPEG_FAILED"
CODE_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
CODE_UPSTREAM_FETCH_FAILED = "UPSTREAM_FETCH_FAILED"


def http_error(status: int, code: str, message: str, **details) -> HTTPException:
    """Build a FastAPI HTTPException with the canonical ErrorBody payload.

    Callers raise this; FastAPI's default exception handler returns
    `{"detail": <our payload>}`. Combined with the global handler in
    server.py the wire shape becomes `{code, message, details}` matching
    openapi.yaml's ErrorBody.
    """
    payload: dict[str, object] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return HTTPException(status_code=status, detail=payload)
