"""URL input/output helpers — `file_url` reads + `output_url` writes.

Reads: stream an HTTP GET into a temp file, return the temp Path.
Writes: stream a local file out via HTTP PUT (presigned URLs welcome).

`httpx` does the actual I/O — supports HTTP/2 + redirects + reasonable
timeouts. SSRF is enforced at the URL parser stage — only http(s),
no localhost / private IPs unless FLICKIES_ALLOW_PRIVATE_FETCH=1.
"""
from __future__ import annotations

import ipaddress
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


_FETCH_TIMEOUT = float(os.environ.get("FLICKIES_FETCH_TIMEOUT_SECS", "300"))
_TRUTHY = frozenset({"1", "true", "yes", "on"})


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
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    raise http_error(
                        502,
                        CODE_UPSTREAM_FETCH_FAILED,
                        f"upstream GET {url} returned {resp.status_code}",
                    )
                with p.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
    except httpx.HTTPError as e:
        try:
            p.unlink()
        except OSError:
            pass
        raise http_error(502, CODE_UPSTREAM_FETCH_FAILED, str(e)) from e
    return p


async def put_file(src: Path, url: str) -> int:
    """Stream a local file to a presigned PUT URL. Returns bytes uploaded."""
    _validate_url(url)
    size = src.stat().st_size
    with src.open("rb") as f:
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.put(
                    url,
                    content=f,
                    headers={"Content-Length": str(size)},
                )
                if resp.status_code >= 400:
                    raise http_error(
                        502,
                        CODE_UPSTREAM_FETCH_FAILED,
                        f"upstream PUT {url} returned {resp.status_code}",
                    )
        except httpx.HTTPError as e:
            raise http_error(502, CODE_UPSTREAM_FETCH_FAILED, str(e)) from e
    return size
