"""File staging layer — /v1/files/{path}.

Files live under FLICKIES_DATA_DIR/files/. Upload via PUT (raw bytes),
download via GET (streamed), delete via DELETE. Path traversal is blocked
at the resolver — any `..` or absolute path in the URL component is
rejected before touching disk.

Most video endpoints reference inputs by `file_path` (FILES_DIR-relative)
and write outputs there too. URL-based inputs/outputs (`file_url` /
`output_url`) bypass this layer.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import AsyncIterator

from flickies.errors import (
    CODE_BAD_REQUEST,
    CODE_NOT_FOUND,
    CODE_PAYLOAD_TOO_LARGE,
    http_error,
)


_MAX_UPLOAD_BYTES_DEFAULT = 5 * 1024 * 1024 * 1024  # 5 GiB
_STREAM_CHUNK = 1024 * 1024  # 1 MiB


def files_dir(data_dir: Path) -> Path:
    """Return FLICKIES_DATA_DIR/files, creating it if absent."""
    d = data_dir / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _max_upload_bytes() -> int:
    raw = os.environ.get("FLICKIES_MAX_UPLOAD_BYTES", "").strip()
    if not raw:
        return _MAX_UPLOAD_BYTES_DEFAULT
    try:
        return int(raw)
    except ValueError:
        return _MAX_UPLOAD_BYTES_DEFAULT


def resolve_safe(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root`, rejecting path traversal.

    Rejects: absolute paths, `..` components, embedded NULs.
    Returns the resolved Path (does NOT require existence).
    """
    if not rel:
        raise http_error(400, CODE_BAD_REQUEST, "empty file path")
    if "\x00" in rel:
        raise http_error(400, CODE_BAD_REQUEST, "null byte in file path")
    p = Path(rel)
    if p.is_absolute():
        raise http_error(400, CODE_BAD_REQUEST, "absolute paths not allowed")
    if any(part == ".." for part in p.parts):
        raise http_error(400, CODE_BAD_REQUEST, "parent-directory components not allowed")
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as e:
        raise http_error(400, CODE_BAD_REQUEST, "path escapes files dir") from e
    return resolved


async def save_stream(
    target: Path,
    chunks: AsyncIterator[bytes],
    *,
    max_bytes: int | None = None,
) -> tuple[int, str]:
    """Stream chunks into target, hashing as we go.

    Returns (bytes_written, sha256_hex). Raises 413 if max_bytes exceeded.
    """
    limit = max_bytes if max_bytes is not None else _max_upload_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    total = 0
    with target.open("wb") as f:
        async for chunk in chunks:
            if not chunk:
                continue
            total += len(chunk)
            if total > limit:
                f.close()
                try:
                    target.unlink()
                except OSError:
                    pass
                raise http_error(
                    413,
                    CODE_PAYLOAD_TOO_LARGE,
                    f"upload exceeded {limit} bytes",
                )
            h.update(chunk)
            f.write(chunk)
    return total, h.hexdigest()


def delete(path: Path) -> None:
    if not path.exists():
        raise http_error(404, CODE_NOT_FOUND, f"file not found: {path.name}")
    if path.is_dir():
        raise http_error(400, CODE_BAD_REQUEST, "refuse to delete a directory")
    path.unlink()


def stat(path: Path) -> dict[str, object]:
    if not path.exists():
        raise http_error(404, CODE_NOT_FOUND, f"file not found: {path.name}")
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime}


async def stream_file(path: Path) -> AsyncIterator[bytes]:
    if not path.exists():
        raise http_error(404, CODE_NOT_FOUND, f"file not found: {path.name}")
    with path.open("rb") as f:
        while True:
            chunk = f.read(_STREAM_CHUNK)
            if not chunk:
                break
            yield chunk
