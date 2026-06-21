"""Logging setup — JSON to stderr + rotating file, ContextVar scope, redactor.

Implements the canonical contract from ~/.claude/rules/06-logging.md +
~/.claude/rule-details/{logging,python/logging}.md:

  - JSON output via python-json-logger.
  - Every line: time (ISO 8601 UTC sub-ms), level, name, file, line, func,
    msg + scope attrs (trace_id, request_id, ...).
  - Two handlers always: stderr + RotatingFileHandler at FLICKIES_LOG_FILE
    (default /data/logs/flickies.log).
  - `with_scope(**kv)` layers attrs onto the current ContextVar; ScopeFilter
    injects them into every LogRecord.
  - RedactingFormatter masks keys/values matching the secret pattern at
    format time — the "log it liberally; the redactor handles the
    dangerous keys" workhorse.

Module name = `logging_config` (not `logging`) to avoid shadowing stdlib.
"""
from __future__ import annotations

import contextvars
import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger


# ── secret pattern — applied to BOTH keys and string values ────────────────
SECRET_RE = re.compile(
    r"(?i)(password|token|secret|api[_-]?key|authorization|cookie|set-cookie|x-api-key|"
    r"hf_[a-z0-9]{30,}|sk-ant-[a-z0-9-]{20,}|sk-[a-z0-9]{30,})"
)

# Sentinel scope ContextVar. Empty dict default keeps `get()` cheap.
_scope: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "flickies_log_scope", default={}
)


# ── public scope API ────────────────────────────────────────────────────────

def with_scope(**kv: Any) -> contextvars.Token:
    """Layer attrs onto the current scope. Returns a token; pass to reset()."""
    current = _scope.get()
    return _scope.set({**current, **kv})


def reset_scope(token: contextvars.Token) -> None:
    _scope.reset(token)


def get_scope() -> dict[str, Any]:
    return _scope.get()


# ── filter — pulls current scope onto every record ─────────────────────────

class ScopeFilter(logging.Filter):
    """Attach every scope attr onto the LogRecord so the formatter emits them."""

    def filter(self, record: logging.LogRecord) -> bool:
        for k, v in _scope.get().items():
            # Don't overwrite stdlib-reserved fields (e.g. `msg`, `name`).
            if not hasattr(record, k) or k in {
                "trace_id", "request_id", "user_id", "workflow_id",
                "activity_id", "job_id", "correlation_id", "engine_slug",
                "component", "session_id",
            }:
                setattr(record, k, v)
        # Defaults so the JSON output always carries these keys.
        if not hasattr(record, "trace_id"):
            record.trace_id = ""
        if not hasattr(record, "request_id"):
            record.request_id = ""
        return True


# ── redacting JSON formatter ───────────────────────────────────────────────

# Noisy stdlib-emitted fields we don't want in every line.
_DROPPED_FIELDS = frozenset({"taskName", "color_message"})


class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    """JSON output + recursive key+value redaction at format time.

    Override `formatTime` to emit proper ISO 8601 w/ sub-ms — Python's
    stdlib `time.strftime` doesn't understand `%f`, so the parent's
    plumbing leaves the literal in the output.
    """

    def formatTime(  # noqa: N802 — overriding stdlib name
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # sub-ms truncated to 3 digits, trailing Z = UTC.
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        for k in _DROPPED_FIELDS:
            log_record.pop(k, None)
        self._redact(log_record)

    def _redact(self, d: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(d, dict):
            for k in list(d.keys()):
                if isinstance(k, str) and SECRET_RE.search(k):
                    d[k] = "[REDACTED]"
                    continue
                v = d[k]
                if isinstance(v, str) and SECRET_RE.search(v):
                    # Catches `-----BEGIN PRIVATE KEY-----` etc. that leak as values.
                    d[k] = "[REDACTED]"
                else:
                    self._redact(v, depth + 1)
        elif isinstance(d, list):
            for i, v in enumerate(d):
                if isinstance(v, str) and SECRET_RE.search(v):
                    d[i] = "[REDACTED]"
                else:
                    self._redact(v, depth + 1)


# ── entry point ─────────────────────────────────────────────────────────────

_DEFAULT_FMT = (
    "%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d "
    "%(funcName)s %(message)s"
)
_FIELD_RENAMES = {
    "asctime": "time",
    "levelname": "level",
    "name": "logger",
    "filename": "file",
    "lineno": "line",
    "funcName": "func",
    "message": "msg",
}


def _log_file_path() -> Path:
    raw = os.environ.get("FLICKIES_LOG_FILE", "").strip()
    if raw:
        return Path(raw)
    data_dir = os.environ.get("FLICKIES_DATA_DIR", "/data")
    return Path(data_dir) / "logs" / "flickies.log"


def configure_logging() -> None:
    """Wire stderr + rotating file + ScopeFilter + RedactingJsonFormatter.

    Reads from env:
      FLICKIES_LOG_LEVEL (default INFO)
      FLICKIES_LOG_FILE  (default $FLICKIES_DATA_DIR/logs/flickies.log)

    Idempotent — clears existing root handlers before installing ours so
    re-running doesn't double-log.
    """
    level_str = os.environ.get("FLICKIES_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    formatter = RedactingJsonFormatter(
        _DEFAULT_FMT,
        rename_fields=_FIELD_RENAMES,
        datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
        json_ensure_ascii=False,
    )
    scope_filter = ScopeFilter()

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_path = _log_file_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=50_000_000,
                backupCount=5,
                encoding="utf-8",
            )
        )
    except OSError as e:
        # Read-only / permissions: still log to stderr, surface the issue.
        print(
            f"[flickies.logging] file handler disabled: path={log_path} err={e}",
            file=sys.stderr,
        )

    for h in handlers:
        h.setFormatter(formatter)
        h.addFilter(scope_filter)

    root = logging.getLogger()
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)
    root.setLevel(level)

    # Force uvicorn loggers to use the same handlers + format. Without this,
    # uvicorn keeps its own ANSI-coloured plain-text emitter alongside ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        for h in handlers:
            lg.addHandler(h)
        lg.propagate = False
        lg.setLevel(level)
