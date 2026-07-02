"""URL input/output helpers — `file_url` reads + `output_url` writes.

Reads: stream an HTTP GET into a temp file, return the temp Path.
Writes: stream a local file out via HTTP PUT (presigned URLs welcome).

`httpx` does the actual I/O — supports HTTP/2 + redirects + reasonable
timeouts. SSRF is enforced at the URL parser stage — only http(s),
no localhost / private IPs unless FLICKIES_ALLOW_PRIVATE_FETCH=1.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from flickies.errors import (
    CODE_BAD_REQUEST,
    CODE_UPSTREAM_FETCH_FAILED,
    http_error,
)


_log = logging.getLogger("flickies.fetch")


_FETCH_TIMEOUT = float(os.environ.get("FLICKIES_FETCH_TIMEOUT_SECS", "300"))


def loggable_url(url: str) -> str:
    """Scheme://host/path with the query string dropped — safe to log.

    Presigned URLs carry credentials in the query string (`X-Amz-Signature`,
    `?token=`, etc.) that the log redactor's keyword pattern doesn't reliably
    catch. Strip the query entirely; host + path is enough to reconstruct
    which object was fetched without leaking the grant.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _scope_headers() -> dict[str, str]:
    """Forward trace_id + request_id onto outbound calls so the next hop's
    logs correlate with ours (per ~/.claude/rules/06-logging.md scope
    propagation contract)."""
    from flickies.logging_config import get_scope
    s = get_scope()
    out: dict[str, str] = {}
    rid = s.get("request_id")
    tid = s.get("trace_id")
    if rid:
        out["X-Request-Id"] = str(rid)
    if tid:
        out["X-Trace-Id"] = str(tid)
    return out


def _allow_private() -> bool:
    return os.environ.get("FLICKIES_ALLOW_PRIVATE_FETCH", "").strip().lower() in _TRUTHY


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise http_error(400, CODE_BAD_REQUEST, f"unsupported URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise http_error(400, CODE_BAD_REQUEST, "URL missing hostname")
    if _allow_private():
        return
    # SSRF defense: resolve the hostname and reject private / loopback / link-local.
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as e:
        raise http_error(400, CODE_BAD_REQUEST, f"DNS resolution failed: {e}") from e
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            _log.warning(
                "url fetch refused: private/loopback IP",
                extra={"host": parsed.hostname, "addr": addr, "reason": "ssrf_private_ip"},
            )
            raise http_error(
                400,
                CODE_BAD_REQUEST,
                f"URL resolves to private/loopback IP ({addr}); "
                "set FLICKIES_ALLOW_PRIVATE_FETCH=1 to permit",
            )


async def fetch_to_temp(url: str, *, suffix: str = "") -> Path:
    """Download `url` to a NamedTemporaryFile, return its Path.

    Caller is responsible for unlinking. Raises 400 on bad URLs, 502 on
    upstream failure.
    """
    _validate_url(url)
    fd, tmp = tempfile.mkstemp(prefix="flickies-in-", suffix=suffix)
    os.close(fd)
    p = Path(tmp)
    _log.debug("url fetch start", extra={"url": loggable_url(url), "dst": str(p), "timeout_secs": _FETCH_TIMEOUT})
    total = 0
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", url, headers=_scope_headers()) as resp:
                if resp.status_code >= 400:
                    _log.warning(
                        "url fetch failed: upstream error",
                        extra={"url": loggable_url(url), "status": resp.status_code, "reason": "upstream_non_2xx"},
                    )
                    raise http_error(
                        502,
                        CODE_UPSTREAM_FETCH_FAILED,
                        f"upstream GET {url} returned {resp.status_code}",
                    )
                with p.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        f.write(chunk)
    except httpx.HTTPError as e:
        _log.warning(
            "url fetch failed: transport error",
            extra={"url": loggable_url(url), "err": str(e), "reason": "transport_error"},
        )
        try:
            p.unlink()
        except OSError:
            pass
        raise http_error(502, CODE_UPSTREAM_FETCH_FAILED, str(e)) from e
    _log.debug("url fetch complete", extra={"url": loggable_url(url), "dst": str(p), "bytes": total})
    return p


async def put_file(src: Path, url: str) -> int:
    """Stream a local file to a presigned PUT URL. Returns bytes uploaded."""
    _validate_url(url)
    size = src.stat().st_size
    _log.debug("url upload start", extra={"url": loggable_url(url), "src": str(src), "bytes": size})
    with src.open("rb") as f:
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                headers = {"Content-Length": str(size), **_scope_headers()}
                resp = await client.put(url, content=f, headers=headers)
                if resp.status_code >= 400:
                    _log.warning(
                        "url upload failed: upstream error",
                        extra={"url": loggable_url(url), "status": resp.status_code, "reason": "upstream_non_2xx"},
                    )
                    raise http_error(
                        502,
                        CODE_UPSTREAM_FETCH_FAILED,
                        f"upstream PUT {url} returned {resp.status_code}",
                    )
        except httpx.HTTPError as e:
            _log.warning(
                "url upload failed: transport error",
                extra={"url": loggable_url(url), "err": str(e), "reason": "transport_error"},
            )
            raise http_error(502, CODE_UPSTREAM_FETCH_FAILED, str(e)) from e
    _log.debug("url upload complete", extra={"url": loggable_url(url), "bytes": size})
    return size
