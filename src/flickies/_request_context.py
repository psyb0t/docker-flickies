"""Request-scoped context — request_id ContextVar + log filter that
injects it into every LogRecord so JSON logs carry the correlator
without anyone passing it around.

Used by RequestIdMiddleware (sets the contextvar at the boundary) and
the logging config (filter attaches request_id to every record).
"""
from __future__ import annotations

import logging
from contextvars import ContextVar


REQUEST_ID: ContextVar[str] = ContextVar("flickies_request_id", default="-")


def get_request_id() -> str:
    return REQUEST_ID.get()


def set_request_id(rid: str) -> None:
    REQUEST_ID.set(rid)


class RequestIdFilter(logging.Filter):
    """Attach `request_id` to every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True
