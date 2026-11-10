# API design rules

Prefix: API.

The surface: `GET /healthz`, `GET /v1/health`, `GET /v1/engines`, `DELETE /v1/engines/{slug}`, `PUT|GET|DELETE /v1/files/{path}`, `GET /v1/jobs/{job_id}`, `POST /v1/video/{lipsync,restore,trim,concat,transcode,scale,mux_audio,extract_audio,thumbnail_grid,info}`, and the MCP mount at `/v1/mcp`. All routes are in `build_app()` in `src/flickies/server.py`.

## Contract

- **API1:** Every video route takes a JSON body and follows the shared contract: exactly one input (`_resolve_input()`, `file_path` xor `file_url`), exactly one output unless `async_job` (`_validate_output_xor()`), and `_run_or_schedule()` for the sync/async split. Responses are `{path, size}` for `output_path`, `{url, size}` for `output_url`, and `202 {job_id, status: "accepted"}` for async. Never add a route that writes outputs another way.
- **API2:** Staging paths are relative to `files_dir(cfg.data_dir)` (`/data/files`) and always go through `resolve_safe()`; URLs always go through `fetch_to_temp()` or `put_file()` (SEC3). Temp inputs and outputs are unlinked in a `finally`.
- **API3:** A new ffmpeg operation is a method on `FFmpeg` plus a route that calls `_ffmpeg_handler(body, ext, op_factory)`; engine routes call `registry.acquire(slug)` and map `EngineNotRegistered` to 404 `ENGINE_NOT_REGISTERED`.

## Errors

- **API4:** Errors are `{code, message, details?}` with UPPER_SNAKE_CASE codes from `src/flickies/errors.py`; the `StarletteHTTPException`, `NonCommercialOptInRequired` and `RequestValidationError` handlers in `server.py` enforce the shape, and `_status_to_code()` covers bare statuses. Keep the status meanings: 400 bad input, 401 auth, 403 non-commercial gate, 404 missing file, job or engine, 413 upload cap, 422 body not a JSON object, 429 rate limit, 500 ffmpeg or inference failure, 502 upstream fetch or PUT. A new code goes into `errors.py`, `ErrorBody.code.examples` in `openapi.yaml` and the error table in `docs/api.md`.

## Spec and clients

- **API5:** `openapi.yaml` describes every REST route. A route or field change edits `openapi.yaml` and runs `make generate` in the same change, committing `src/flickies/schema/_generated.py`, `pkg/clients/go/client.gen.go` and `pkg/clients/python/flickies-client/` together; never hand-edit them (`make generate-check` fails on drift). Request schemas that combine `allOf` with sibling `properties` lose those properties in the generated clients (`docs/clients.md`); prefer listing properties in the schema itself for new requests.
- **API6:** Request bodies are `dict[str, Any]`; the server does not validate them against the spec. Read optional fields with `.get()` and a default.

## Jobs, webhooks and headers

- **API7:** Async work runs through `JobQueue.submit()` (`src/flickies/jobs.py`); job state is in memory and its public shape is `Job.to_dict()` (`job_id`, `status`, `result`, `error`). Webhooks go through `deliver()` in `src/flickies/webhooks.py`: HMAC-SHA256 over `timestamp + "." + body`, `X-Webhook-Timestamp` and `X-Webhook-Signature: t=<ts>,v1=<hex>`, retries on `_BACKOFF_SCHEDULE`.
- **API8:** `X-Request-Id` and `X-Trace-Id` are accepted only as UUID or ULID (`_shape_valid()` in `src/flickies/middleware.py`), echoed on every response, and forwarded on outbound fetches (`_scope_headers()` in `fetch.py`). `Idempotency-Key` replays responses below 500 per (key, method, path).
