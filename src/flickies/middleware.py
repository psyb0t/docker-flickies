"""ASGI middleware — request_id, rate limiting, idempotency.

All three are pure-stdlib ASGI middleware so flickies stays dep-light.

- RequestIdMiddleware: pull X-Request-Id from headers OR generate uuid4,
  stash on ContextVar + echo back on the response.
- RateLimitMiddleware: per-IP token bucket. Defaults to 60 req/min,
  configurable via FLICKIES_RATE_LIMIT_PER_MIN.
- IdempotencyMiddleware: dedupe POST writes by Idempotency-Key header.
  In-memory LRU keyed on (key, method, path) → cached (status, body).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import OrderedDict

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from flickies._request_context import set_request_id


_log = logging.getLogger("flickies.middleware")

_X_REQUEST_ID_HEADER = b"x-request-id"
_IDEMPOTENCY_HEADER = b"idempotency-key"


def _client_ip(scope: Scope) -> str:
    # Honour X-Forwarded-For if present (single hop — first value).
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return value.decode("latin-1").split(",", 1)[0].strip()
    client = scope.get("client")
    if client:
        return str(client[0])
    return "-"


def _get_header(scope: Scope, name: bytes) -> str | None:
    for hname, hvalue in scope.get("headers", []):
        if hname == name:
            return hvalue.decode("latin-1").strip()
    return None


# ── request id ────────────────────────────────────────────────────────────

class RequestIdMiddleware:
    """Echo X-Request-Id back and stash it on a ContextVar for logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        rid = _get_header(scope, _X_REQUEST_ID_HEADER) or uuid.uuid4().hex
        set_request_id(rid)

        async def send_with_rid(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((_X_REQUEST_ID_HEADER, rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_rid)


# ── rate limit (per-IP token bucket) ─────────────────────────────────────

def _rate_per_min() -> int:
    raw = os.environ.get("FLICKIES_RATE_LIMIT_PER_MIN", "60").strip()
    try:
        n = int(raw)
        return max(0, n)
    except ValueError:
        return 60


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float, now: float) -> None:
        self.tokens = capacity
        self.last_refill = now


class RateLimitMiddleware:
    """Per-IP token bucket. 0 = disabled."""

    _EXEMPT_PATHS = frozenset({"/healthz"})

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.capacity = float(_rate_per_min())
        self.refill_per_sec = self.capacity / 60.0
        self.buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    def _take(self, ip: str) -> bool:
        if self.capacity <= 0:
            return True  # disabled
        now = time.monotonic()
        b = self.buckets.get(ip)
        if b is None:
            b = _Bucket(self.capacity, now)
            self.buckets[ip] = b
        else:
            elapsed = now - b.last_refill
            if elapsed > 0:
                b.tokens = min(self.capacity, b.tokens + elapsed * self.refill_per_sec)
            b.last_refill = now
        if b.tokens < 1.0:
            return False
        b.tokens -= 1.0
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.capacity <= 0:
            await self.app(scope, receive, send)
            return
        if scope.get("path", "") in self._EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        ip = _client_ip(scope)
        async with self._lock:
            ok = self._take(ip)
        if not ok:
            _log.warning("rate_limit: ip=%s path=%s", ip, scope.get("path", ""))
            body = json.dumps({
                "code": "RATE_LIMITED",
                "message": "rate limit exceeded; back off",
            }).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"retry-after", b"60"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


# ── idempotency ──────────────────────────────────────────────────────────

def _idempotency_cap() -> int:
    raw = os.environ.get("FLICKIES_IDEMPOTENCY_CACHE_SIZE", "1024").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1024


class IdempotencyMiddleware:
    """Dedupe POST writes by Idempotency-Key header.

    Cache shape: LRU keyed on (key, method, path) → (status, [headers], body).
    Replays the cached response when the same key reappears.
    Cap is in-memory; 0 = disabled.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.cap = _idempotency_cap()
        self.cache: OrderedDict[tuple[str, str, str], tuple[int, list, bytes]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.cap <= 0 or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        key = _get_header(scope, _IDEMPOTENCY_HEADER)
        if not key:
            await self.app(scope, receive, send)
            return

        ck = (key, scope.get("method", ""), scope.get("path", ""))
        async with self._lock:
            cached = self.cache.get(ck)
        if cached is not None:
            status, headers, body = cached
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        # Capture response so we can cache it.
        captured_status = 0
        captured_headers: list = []
        captured_body = bytearray()

        async def capturing_send(message: Message) -> None:
            nonlocal captured_status, captured_headers
            if message["type"] == "http.response.start":
                captured_status = int(message["status"])
                captured_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    captured_body.extend(chunk)
            await send(message)

        await self.app(scope, receive, capturing_send)

        # Only cache 2xx/4xx terminal responses.
        if 200 <= captured_status < 500:
            async with self._lock:
                self.cache[ck] = (captured_status, captured_headers, bytes(captured_body))
                while len(self.cache) > self.cap:
                    self.cache.popitem(last=False)
