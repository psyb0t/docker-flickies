"""flickies entrypoint — `python -m flickies`."""
from __future__ import annotations

import logging
import os

import uvicorn

from flickies._request_context import RequestIdFilter
from flickies.config import load
from flickies.server import build_app


def _configure_logging() -> None:
    level = os.environ.get("FLICKIES_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s",
        )
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
    # Uvicorn uses its own loggers — share the filter so access lines carry request_id.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.addHandler(handler)
        lg.propagate = False


def main() -> None:
    _configure_logging()
    cfg = load()
    uvicorn.run(build_app(), host=cfg.host, port=cfg.port, log_config=None)


if __name__ == "__main__":
    main()
