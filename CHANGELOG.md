# Changelog

All notable changes per release. Versions follow [semver](https://semver.org)
pre-1.0 conventions: minor bumps may include breaking REST changes (called
out explicitly), patch bumps are docs / build / fixes only.

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
