"""Webhook delivery — HMAC-signed POST with exponential backoff retry.

Sender pattern from `~/.claude/rule-details/securing-the-app.md`:
  - HMAC-SHA256 over `timestamp + "." + body`
  - Per-recipient secret (FLICKIES_WEBHOOK_SECRET env, single-tenant for now)
  - Headers: `X-Webhook-Timestamp`, `X-Webhook-Signature: t={ts},v1={hex}`
  - Retry on non-2xx with exponential backoff (30s, 1m, 5m, 30m, 2h, 12h)
  - Dead-letter logged after final retry
  - Idempotency: receiver MUST de-dupe on (timestamp, signature)

Used by JobQueue when `webhook_url` is supplied on async job submit.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import httpx


_log = logging.getLogger("flickies.webhooks")


_BACKOFF_SCHEDULE = (30.0, 60.0, 300.0, 1800.0, 7200.0, 43200.0)  # seconds


def _secret() -> bytes:
    return os.environ.get("FLICKIES_WEBHOOK_SECRET", "").encode("utf-8")


def _sign(body: bytes) -> tuple[str, str]:
    secret = _secret()
    ts = str(int(time.time()))
    msg = ts.encode("ascii") + b"." + body
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest() if secret else ""
    return ts, sig


async def deliver(url: str, payload: dict[str, Any]) -> bool:
    """POST payload to url with HMAC signature + exponential retry.

    Returns True on first successful 2xx, False after all retries exhausted.
    """
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ts, sig = _sign(body)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": ts,
        "X-Webhook-Signature": f"t={ts},v1={sig}",
    }

    attempt = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, content=body, headers=headers)
            if 200 <= resp.status_code < 300:
                _log.info(
                    "webhook delivered",
                    extra={
                        "url": url,
                        "status": resp.status_code,
                        "attempt": attempt + 1,
                    },
                )
                return True
            _log.warning(
                "webhook non-2xx",
                extra={
                    "url": url,
                    "status": resp.status_code,
                    "attempt": attempt + 1,
                    "reason": "upstream_non_2xx",
                },
            )
        except httpx.HTTPError as e:
            _log.warning(
                "webhook transport error",
                extra={
                    "url": url,
                    "err": str(e),
                    "attempt": attempt + 1,
                    "reason": "transport_error",
                },
            )

        if attempt >= len(_BACKOFF_SCHEDULE):
            _log.error(
                "webhook dead-letter",
                extra={
                    "url": url,
                    "attempts": attempt + 1,
                    "body_preview": body[:512].decode("utf-8", errors="replace"),
                    "reason": "max_retries_exhausted",
                },
            )
            return False
        await asyncio.sleep(_BACKOFF_SCHEDULE[attempt])
        attempt += 1
