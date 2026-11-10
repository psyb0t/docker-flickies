# Python code rules

Prefix: PY.

Covers first-party code in `src/flickies/`. `src/flickies/_vendor/` is upstream code: change it only to make it run here, and say so in the change.

## Style and typing

- **PY1:** Every module in `src/flickies/` starts with `from __future__ import annotations` (only the two `__init__.py` files lack it).
- **PY2:** ruff is the linter and formatter: line length 100, rules `E F W I B UP ARG SIM C4`, `E501` ignored (`[tool.ruff]` in `pyproject.toml`). pyright checks `src` with `reportMissingImports = "none"` because the dev image has no ML stack. Both skip `src/flickies/_vendor/` and `src/flickies/schema/_generated.py`.

## Configuration

- **PY5:** Settings are environment variables prefixed `FLICKIES_`. `src/flickies/config.py` `load()` owns the core ones and raises on a missing engines file or a bad port. Others are read with `os.environ.get` in the module that uses them, through a small helper (`_max_upload_bytes()`, `_rate_per_min()`, `_idle_unload_secs()`): booleans are true for `1`, `true`, `yes`, `on` (the `_TRUTHY` frozenset, case-insensitive), and a bad number falls back to the default. Follow that pattern for a new setting and document it (DOC2).

## Async and blocking work

- **PY6:** External programs run with `asyncio.create_subprocess_exec` (`_run()` in `src/flickies/ffmpeg.py`), except the GFPGAN audio remux, which runs inside its worker thread.
- **PY7:** Import heavy libraries (torch, cv2, numpy, diffusers, gfpgan, huggingface_hub) inside the function that needs them, never at module top: the dev image has none of them and the CPU image lacks the LatentSync stack, and `server.py` imports every engine module at startup.

## Errors

- **PY8:** Raise client and server errors with `http_error(status, CODE_*, message, **details)` from `src/flickies/errors.py`, which produces the `{code, message, details}` envelope. Do not build envelopes by hand (the middleware 401 and 429 bodies are the exceptions, since they answer before FastAPI).
- **PY10:** Broad `except Exception` (job runner, sweeper loop, prefetch, engine inference wrapper, unload cleanup) is logged and marked `# noqa: BLE001`. Engine wrappers re-raise `HTTPException` untouched before wrapping anything else in a 500 (`Wav2Lip.lipsync`).

## Logging

- **PY11:** `configure_logging()` in `src/flickies/logging_config.py` owns the root and uvicorn handlers. Do not add handlers or call `logging.basicConfig` elsewhere, and do not `print()` in `src/` (the only print is the file-handler fallback there).
- **PY12:** Loggers are named explicitly: `logging.getLogger("flickies.<module>")` and `"flickies.engines.<engine>"`; `_registry.py` uses `__name__`, which lands in the same tree.
- **PY13:** Warnings and rejections carry a `reason` field in snake_case in `extra` (`"reason": "ssrf_private_ip"`, `"reason": "bucket_empty"`). URLs are logged through `loggable_url()` (SEC4).
