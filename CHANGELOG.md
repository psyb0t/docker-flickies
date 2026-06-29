# Changelog

All notable changes per release. Versions follow [semver](https://semver.org)
pre-1.0 conventions: minor bumps may include breaking REST changes (called
out explicitly), patch bumps are docs / build / fixes only.

## [0.3.0] - 2026-06-29

Frame-accurate `precise` flag on the ffmpeg-ops `trim` + `concat` endpoints.

### Added

- **`precise: bool` (default `false`) on `POST /v1/video/trim`**
  (`openapi.yaml` → `VideoTrimRequest`, `src/flickies/ffmpeg.py`,
  `src/flickies/server.py`, MCP `trim` tool in `src/flickies/mcp_server.py`).
  - `precise=false` (default) keeps the existing `-c copy` stream-copy
    behavior — fast, but ffmpeg can only cut on keyframe boundaries and
    `start_sec` snaps to the nearest keyframe, potentially eating up to
    one GOP (~seconds at 30 fps / 250-frame GOP) of leading content.
  - `precise=true` re-encodes via `libx264 -crf 18 -preset veryfast`
    + `aac -b:a 192k` for frame-accurate boundaries. Single-generation
    re-encode, visually transparent. Slower than stream-copy; use when
    you need the exact requested start (e.g. stitching short speech
    clips at arbitrary timestamps).
- **`precise: bool` (default `false`) on `POST /v1/video/concat`**
  (same files). Default keeps the concat demuxer with `-c copy` —
  requires all inputs to share codec / timebase / SAR. `precise=true`
  re-encodes through the concat demuxer with uniform x264 + AAC params
  so mixed-encoder inputs join cleanly.
- Both MCP tools (`trim`, `concat`) gain a `precise` boolean parameter
  with docstrings explaining the tradeoff.

### Changed

- **`openapi.yaml` `info.version` bumped to `0.3.0`** (spec rev tracks
  package).
- Regenerated typed clients from the spec:
  - `src/flickies/schema/_generated.py` (Pydantic models — `VideoTrimRequest`
    + `VideoConcatRequest` carry the new `precise` field).
  - `pkg/clients/python/flickies-client/.../video_trim_request.py`
    (sync + async Python client).

### Notes

- The Go client struct `VideoTrimRequest` / `VideoConcatRequest` does
  not surface `start_sec` / `end_sec` / `precise` due to a pre-existing
  `oapi-codegen` limitation with `allOf`-composed schemas (the inline
  `properties:` block on the composed type is dropped). Same behavior
  as prior releases for `start_sec` / `end_sec`; not new. Go callers
  marshal the body via `map[string]any` or a hand-written struct in
  the meantime.
- Pure feature addition; no breaking changes; defaults preserve prior
  endpoint behavior exactly.

## [0.2.0] - 2026-06-21

Operational hardening pass — proper structured logging, boot-time weight
prefetch, HuggingFace-cache reusable layout, bearer auth verified live.
All ML pipelines remain live-verified on RTX 3060 12 GB.

### Added

- **Structured JSON logging** (`src/flickies/logging_config.py`) per
  `~/.claude/rules/06-logging.md`:
  - `RedactingJsonFormatter` (subclass of `python-json-logger`) — recursive
    key + value redaction of `password|token|secret|api[_-]?key|authorization|cookie|set-cookie|hf_*|sk-ant-*|sk-*` at format time. Keys that match map to `[REDACTED]`; string values that match (e.g. `-----BEGIN PRIVATE KEY-----`) are also redacted.
  - ContextVar-backed `with_scope(**kv)` / `get_scope()` / `ScopeFilter`. Every
    log record carries `trace_id` + `request_id` (plus any custom scope attrs).
  - Two handlers always: `StreamHandler(stderr)` + `RotatingFileHandler`
    at `FLICKIES_LOG_FILE` (default `$FLICKIES_DATA_DIR/logs/flickies.log`,
    50 MB × 5 backups).
  - ISO 8601 UTC sub-ms `time` field (`2026-06-21T22:20:36.163Z`).
  - Forces uvicorn's own loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`)
    to use the same handlers — no ANSI-colour plain-text leak.
  - Drops noisy stdlib fields (`taskName`, `color_message`).
- **Audited every `_log.X("…%s", v)` call site** in the codebase (~30 sites)
  and rewrote to `extra={…}` structured fields per
  `~/.claude/rule-details/python/logging.md`. Includes a `reason` enum-style
  field on every filter / fall-back branch.
- **Trace + Request ID hardening** in `RequestIdMiddleware`:
  - Validates inbound `X-Request-Id` shape (UUID v4 OR ULID, max 64 chars,
    no newlines) before echoing. Garbage shape → mints a fresh UUID v4 (no
    log-injection / forged-correlator vectors).
  - Also accepts `X-Trace-Id` separately; defaults to `request_id` if absent.
  - Both echoed back on `X-Request-Id` + `X-Trace-Id` response headers.
- **Outbound HTTP propagation** (`src/flickies/fetch.py`): every `httpx`
  GET (URL fetch) and PUT (output upload) now forwards the current
  `X-Request-Id` + `X-Trace-Id` so the next hop's logs correlate with ours.
- **Boot-time weight prefetch** (`src/flickies/prefetch.py`):
  - Runs from `entrypoint.sh` BEFORE uvicorn starts.
  - `FLICKIES_ENABLED_ENGINES=wav2lip,gfpgan` → prefetch those slugs only.
  - `FLICKIES_PREFETCH_ALL=1` → prefetch every applicable engine
    (respects `cuda_only` + `noncommercial` gates).
  - `FLICKIES_OFFLINE=1` → skip prefetch (operator stages weights manually).
  - First-request latency drops from "~2.5 min cold weight pull" to
    "<200 ms" when prefetch is opted-in at boot.
- **HuggingFace cache, full-repo blob layout** for every model engine:
  - `wav2lip` / `wav2lip-gan` → `snapshot_download("Nekochu/Wav2Lip")`
  - S3FD face detector → `snapshot_download("ByteDance/LatentSync-1.5")`
    (LatentSync's repo permanently bundles s3fd in `auxiliary/`, saves us
    standing up a mirror just for it)
  - `gfpgan` → `snapshot_download("leonelhs/gfpgan")`
  - `latentsync-1.5` → `snapshot_download("ByteDance/LatentSync-1.5")`
  - **No `allow_patterns`** — full repo cloned via standard HF cache so
    `/data/hf/hub/models--<org>--<name>/{blobs,snapshots,refs}/…` is
    reusable by any other HF-aware tool, not just flickies.
  - Replaces the prior raw `urllib.request.urlretrieve` calls + the 5 GB
    `model.tar` tarball for LatentSync — both now obsolete.
- **`FLICKIES_AUTH_TOKEN` live-verified** end-to-end on both CPU + CUDA
  images. Any string works (`testme`, `AAAAAA`, UUID, output of
  `openssl rand -hex 32`, etc.). Constant-time `hmac.compare_digest`.
  `/healthz` exempt (probe-friendly).
- **Auth posture announcement** in `entrypoint.sh` boot log — operators
  see immediately whether bearer auth is enforced or disabled.

### Changed

- **Versioning compliance**: `pyproject.toml` `[project] version` is the
  single canonical source. `src/flickies/__version__.py` derives via
  `importlib.metadata.version("flickies")` (was hand-edited). `make
  version` prints the tag for sanity-check before tagging. Makefile build
  targets tag both `:vX.Y.Z` AND `:latest` (was only `:local`).
- **OpenAPI `info.version` bumped to `0.2.0`** (spec rev tracks package).
- **`python-json-logger==2.0.7`** added to lightweight runtime deps in
  `pyproject.toml` + `uv.lock`.
- **`huggingface_hub==0.30.2`** added to `heavy-deps-cpu.in` (was only
  transitive on CUDA via diffusers — explicit pin keeps the CPU image's
  wav2lip + gfpgan + s3fd downloaders working).

### Fixed

- `%(asctime)s` `%f` literal leaked into the `time` field — overrode
  `RedactingJsonFormatter.formatTime` to emit proper sub-ms ISO 8601.
- Inbound free-form `X-Request-Id` was echoed verbatim — small log-injection
  risk if the value contained newlines or huge payloads. Now shape-validated.
- Rate-limit middleware float-precision bug from a prior session re-verified
  (regression test in `test_middleware.py`).

### Removed

- `src/flickies/_request_context.py` — superseded by `logging_config.py`'s
  `with_scope` ContextVar.

### Internal

- 27/27 tests pass; new `test_request_id_rejects_invalid_shape` test added.
- Live-verified on RTX 3060 (3.1–9.6 GB VRAM depending on engine).
- HF cache live-inspected — every entry is a proper blob/snapshot symlink
  pair (verified `ls -la /data/hf/hub/models--*/snapshots/<rev>/`).

## [0.1.0] - 2026-06-21

Initial public release. Self-hosted video toolkit modelled after audiolla /
talkies / ibkr-httpapi.

### Engines (all live-verified on RTX 3060 12 GB)

- **wav2lip / wav2lip-gan** (Rudrabha/Wav2Lip, vendored under `src/flickies/_vendor/wav2lip/`,
  CPU + CUDA). Modernized for librosa 0.10+. Loads weights from
  `FLICKIES_DATA_DIR/models/wav2lip/`; auto-downloads from the Nekochu
  HuggingFace mirror on first call. CPU ~44s / GPU ~22s on a 3s clip.
  Non-commercial gate (`FLICKIES_ENABLE_NONCOMMERCIAL=1`) enforced before
  model load.
- **gfpgan** (TencentARC/GFPGAN v1.4, Apache-2.0, CUDA). Frame-by-frame
  restore via `gfpgan.GFPGANer`; audio preserved via ffmpeg mux. ~49s on a
  6s clip, ~4.2 GB VRAM. Image builds patch `basicsr`'s
  `torchvision.transforms.functional_tensor` import at build time.
- **latentsync-1.5** (bytedance/LatentSync, Apache-2.0, CUDA, fp16).
  Full upstream vendored under `src/flickies/_vendor/latentsync_pkg/`.
  Auto-downloads the 5 GB `model.tar` from `weights.replicate.delivery` +
  extracts on first call. ~170s on a 6s clip, ~9.6 GB VRAM peak (fits the
  12 GB ceiling).

### Surface

Every public route under `/v1/`. Plural-noun REST + action endpoints for
non-CRUD. Error envelope = `{code, message, details}` w/ UPPER_SNAKE_CASE
codes (`BAD_REQUEST`, `UNAUTHORIZED`, `NOT_FOUND`, `NONCOMMERCIAL_GATE_REFUSED`,
`RATE_LIMITED`, `VALIDATION_FAILED`, `FFMPEG_FAILED`, `INTERNAL_SERVER_ERROR`).

- Lipsync: `POST /v1/video/lipsync`
- Restore: `POST /v1/video/restore`
- Video transform: `POST /v1/video/{trim,concat,transcode,scale,mux_audio,extract_audio,thumbnail_grid}`
  — pure ffmpeg, CPU. `transcode` absorbs gif + fps + codec change.
- Info: `POST /v1/video/info` — ffprobe metadata.
- Files: `PUT/GET/DELETE /v1/files/{path}` (octet-stream upload, path-traversal blocked).
- Jobs: `POST` any video-producing route with `async_job=true` returns 202
  + job_id; poll `GET /v1/jobs/{job_id}`. Optional `webhook_url` fires an
  HMAC-signed POST on completion (exponential-backoff retry, dead-letter).
- Engines: `GET /v1/engines` lists; `DELETE /v1/engines/{slug}` evicts.
- Health: `GET /v1/health` (versioned) + `GET /healthz` (probe, auth-exempt).

### MCP

`/v1/mcp` exposes 11 tools via streamable-HTTP JSON-RPC: `list_engines`,
`info`, `lipsync`, `restore`, `transcode`, `trim`, `concat`, `scale`,
`mux_audio`, `extract_audio`, `thumbnail_grid`. Lifespan-wired
`session_manager` so requests run inside the FastAPI app's task group.

### Generated clients (spec-first)

`openapi.yaml` is the single source of truth (OAS 3.0.3 — 3.1 incompatible
with `oapi-codegen` upstream).

- `src/flickies/schema/_generated.py` — Pydantic v2 models (37 symbols)
  via `datamodel-codegen`. Hand-written `__init__.py` re-exports + xor
  validators.
- `pkg/clients/go/client.gen.go` — typed Go client via `oapi-codegen`.
  Standalone module: `go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest`.
- `pkg/clients/python/flickies-client/` — sync + async Python client via
  `openapi-python-client`. Pip-installable as git subdir.

### Middleware

- `BearerAuthMiddleware` — optional, enforced when `FLICKIES_AUTH_TOKEN` is set.
- `RequestIdMiddleware` — generate UUID4 if absent, echo `X-Request-Id`,
  thread through every log line via ContextVar.
- `RateLimitMiddleware` — per-IP token bucket (default 60 req/min,
  configurable via `FLICKIES_RATE_LIMIT_PER_MIN`). `/healthz` exempt.
  Returns 429 + `Retry-After` on overflow.
- `IdempotencyMiddleware` — LRU-cached POST replays keyed on
  `(Idempotency-Key, method, path)`.

### Engine registry

One GPU pool, one resident ML engine at a time. Lazy load + **hot-swap
eviction** (request engine Y → if engine X is loaded and X≠Y, X is
unloaded before Y loads). Idle sweeper unloads after
`FLICKIES_IDLE_UNLOAD_SECS` (default 600s). ffmpeg + ffprobe are NOT
engines — plain singleton at `app.state.ffmpeg`.

### Supply chain

- `uv.lock` (673 lines) — hash-verified light runtime deps via
  `uv sync --frozen`.
- `requirements-heavy-cpu.txt` (1445 lines) — pinned torch CPU + cv2 +
  librosa + numpy + numba + scipy + soundfile + tqdm + GFPGAN stack.
- `requirements-heavy-cuda.txt` (2324 lines) — same plus LatentSync stack:
  diffusers, transformers, mediapipe, decord, kornia, insightface,
  onnxruntime-gpu, accelerate, einops, ffmpeg-python, lpips, scenedetect,
  omegaconf, DeepCache, face-alignment.
- `scripts/compile_heavy_deps.sh` — `uv pip compile --generate-hashes`
  driver, `exclude-newer` gate, dual CPU/CUDA variants.
- `[tool.uv].exclude-newer` floor at UTC-midnight 7 days ago (bumped
  automatically by `make pkg-*` targets via `scripts/bump_exclude_newer.sh`).

### Versioning (per `versioning-a-project.md`)

- Canonical source = `pyproject.toml` `[project] version`.
- Runtime `__version__` derives via `importlib.metadata.version("flickies")`
  — never hardcoded.
- FastAPI `app.version` inherits → OpenAPI `info.version` matches.
- Makefile `VERSION` derived from `pyproject.toml`; `make build` tags both
  `:v0.1.0` and `:latest` (same for `:v0.1.0-cuda` / `:latest-cuda`).
- `make version` prints `v0.1.0` for sanity-check before tagging.

### Docker

- `Dockerfile` (CPU) — `python:3.12-slim-bookworm` + ffmpeg + light deps
  via `uv sync --frozen` + heavy stack via `uv pip install`. basicsr patched
  at build time.
- `Dockerfile.cuda` — `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` +
  deadsnakes py3.12 + build-essential + cu124 wheels.
- `Dockerfile.dev` — sandboxed lint + test + codegen tooling.

### CI

- `.github/workflows/pipeline.yml` — calls
  `psyb0t/reusable-github-workflows/docker-image-workflow.yml` (CPU + CUDA).
- `.github/workflows/collaborators-only.yml` — locks external PRs.

### Known gaps / out of scope

- `--require-hashes` is DISABLED in the heavy-deps install. A handful of
  torch transitives (`jinja2`, `filelock`, `fsspec`) don't get hashes
  captured under `uv 0.11.15` + pytorch wheel index +
  `--extra-index-url` combo. Version pins + `exclude-newer` are the
  supply-chain backstop today. TODO: revisit when uv handles
  cross-index transitive-hash capture.
- aigate compose entry intentionally not included.
