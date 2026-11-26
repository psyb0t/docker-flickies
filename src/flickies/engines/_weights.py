from __future__ import annotations

from pathlib import Path


def cached_snapshot(repo: str, *required: str, offline: bool) -> Path:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        local = Path(snapshot_download(repo_id=repo, local_files_only=True))
    except LocalEntryNotFoundError:
        if offline:
            raise
    else:
        if all((local / name).is_file() for name in required):
            return local
        if offline:
            raise FileNotFoundError(f"cached {repo} snapshot is missing required files")
    return Path(snapshot_download(repo_id=repo))
