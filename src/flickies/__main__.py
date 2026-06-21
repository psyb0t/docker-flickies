"""flickies entrypoint — `python -m flickies`."""
from __future__ import annotations

import uvicorn

from flickies.config import load
from flickies.logging_config import configure_logging
from flickies.server import build_app


def main() -> None:
    configure_logging()
    cfg = load()
    uvicorn.run(build_app(), host=cfg.host, port=cfg.port, log_config=None)


if __name__ == "__main__":
    main()
