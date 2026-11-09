# AGENTS.md

Guide for coding agents working on this repository. If you only want to call a running flickies server from an agent, read [.agents/skills/flickies/SKILL.md](.agents/skills/flickies/SKILL.md) instead; this file is about changing the code.

The project rules live in `.agents/rules/`, one file per topic. They are authoritative for this repository.

## Agent setup

This repository expects the psyb0t rig (`.claude-rig`, or `.codex-rig` once that exists).

`CLAUDE.md` is a committed symlink to `AGENTS.md`, and `.claude` is a committed symlink to `.agents`, so Claude Code reads the same instructions, rules and skills as Codex. Claude's Edit and Write tools refuse to write through a symlink: edit `AGENTS.md` and `.agents/rules/*.md` directly, never the paths under `CLAUDE.md` or `.claude/`.

## What it is

flickies is a self-hosted video API in one Docker image: lipsync (LatentSync 1.5, Wav2Lip, Wav2Lip-GAN), GFPGAN v1.4 face restore, and ffmpeg operations (trim, concat, transcode including GIF, scale, mux audio, extract audio, thumbnail grid, ffprobe info), with server-side file staging, in-process async jobs, HMAC-signed webhooks and an MCP endpoint at `/v1/mcp`.

It keeps one ML engine resident at a time on limited VRAM (hot-swap eviction plus an idle sweeper), downloads weights from Hugging Face on demand, and ships as a CPU image and a CUDA image. It is the video sibling of docker-audiolla and docker-talkies and shares their JSON contract and Makefile shape.

## Architecture

- **One FastAPI process.** `src/flickies/__main__.py` configures logging, loads config and runs uvicorn on `build_app()` from `src/flickies/server.py`, which builds the registry, the job queue, the ffmpeg helper, the middleware stack, the MCP mount, the error handlers and every route.
- **Config.** `src/flickies/config.py` `load()` reads the core settings (host, port, device, engines file, data dir, enabled engines, non-commercial flag) and fails fast on a missing engines file or a bad port. Every other setting is read with `os.environ.get` in the module that uses it (see PY5).
- **Engines.** `engines.json` maps a slug to an `executor`; `_EXECUTOR_MAP` in `server.py` turns `wav2lip`, `latentsync` and `gfpgan` into the classes in `src/flickies/engines/`. `Registry` in `src/flickies/engines/_registry.py` loads lazily, evicts the resident engine when another is acquired, and runs the idle sweeper. `_license_gate.py` refuses Wav2Lip without `FLICKIES_ENABLE_NONCOMMERCIAL`.
- **ffmpeg is not an engine.** `FFmpeg` in `src/flickies/ffmpeg.py` is a plain singleton on `app.state.ffmpeg`; every call goes through `_run()`.
- **Input/output contract.** `_resolve_input()` (`file_path` xor `file_url`), `_validate_output_xor()` and `_run_or_schedule()` in `server.py` implement it for every video route. Paths go through `resolve_safe()` (`src/flickies/files.py`), URLs through `fetch_to_temp()` and `put_file()` (`src/flickies/fetch.py`).
- **Async jobs.** `JobQueue` (`src/flickies/jobs.py`) runs work as an asyncio task in memory; `deliver()` (`src/flickies/webhooks.py`) posts the final state with an HMAC signature and backoff retries.
- **Middleware.** Outermost to innermost: `RequestIdMiddleware`, `RateLimitMiddleware`, `IdempotencyMiddleware` (`src/flickies/middleware.py`), then `BearerAuthMiddleware` (`src/flickies/auth.py`, only when `FLICKIES_AUTH_TOKEN` is set).
- **MCP.** `build_mcp_server()` (`src/flickies/mcp_server.py`) builds a stateless FastMCP server with 11 tools, mounted at `/v1/mcp`.
- **Boot.** `entrypoint.sh` sets defaults (`FLICKIES_HOST=0.0.0.0`), aliases the Hugging Face token variables, patches basicsr if needed, runs `python -m flickies.prefetch`, then `exec python -m flickies`.
- **Agent integrations.** `.agents/skills/flickies/` is the agent skill; `.agents/plugins/flickies/` is an OpenClaw plugin (`bin/cli.js` runs `mcp-remote` against `$FLICKIES_URL/v1/mcp`); `.agents/.claude-plugin/` and `.agents/.codex-plugin/` hold the plugin manifests; `server.json` is the MCP Registry entry.

Data flow:

```text
engines.json -> config.load() -> _build_registry() -> Registry
entrypoint.sh -> prefetch.py -> snapshot_download -> /data/hf

client -> RequestId -> RateLimit -> Idempotency -> BearerAuth -> route
  /v1/video/lipsync, /restore   -> registry.acquire(slug) -> _run_or_schedule -> engine
  /v1/video/<ffmpeg op>, /info  -> _ffmpeg_handler -> _run_or_schedule -> FFmpeg._run
  _run_or_schedule: sync -> output_path | output_url
                    async_job -> JobQueue -> /data/files/jobs/<uuid>.<ext> (+ webhook)
  /v1/mcp (FastMCP)             -> same registry, FFmpeg and files helpers
```

## Stack

- Language: Python 3.12 in every image (`requires-python = ">=3.10,<3.13"` in `pyproject.toml`).
- Framework: FastAPI and uvicorn, the `mcp` SDK (FastMCP), httpx, python-json-logger.
- ML: torch 2.5.1, OpenCV, librosa, GFPGAN 1.3.8 (basicsr, facexlib) in both images; diffusers, transformers, mediapipe, insightface and the rest of the LatentSync stack in the CUDA image only. Vendored source under `src/flickies/_vendor/` (LatentSync 1.5, Wav2Lip).
- Packaging: hatchling; light dependencies in `uv.lock`, the ML stack in compiled `requirements-heavy-cpu.txt` and `requirements-heavy-cuda.txt`.
- Deploy: `psyb0t/flickies:<tag>` (CPU, `Dockerfile`) and `psyb0t/flickies:<tag>-cuda` (`Dockerfile.cuda`), both `linux/amd64`, built by `.github/workflows/pipeline.yml`. No compose file ships.
- Docs: Jekyll with just-the-docs under `docs/`, published by GitHub Pages from `main` `/docs`.
- CI: GitHub Actions through `psyb0t/reusable-github-workflows` at `@master`.

## Layout

| Path | What it owns |
| --- | --- |
| `src/flickies/server.py` | App factory, routes, input/output contract, async scheduling, error envelope handlers, `/healthz`. |
| `src/flickies/mcp_server.py` | FastMCP server and its 11 tools. |
| `src/flickies/engines/` | `base.py` (Engine lifecycle), `_registry.py`, `_license_gate.py`, `wav2lip.py`, `latentsync.py`, `gfpgan.py`. |
| `src/flickies/ffmpeg.py` | Every ffmpeg and ffprobe invocation. |
| `src/flickies/files.py`, `src/flickies/fetch.py` | Staging paths, upload cap, streaming; URL fetch, presigned PUT, SSRF guard, `loggable_url()`. |
| `src/flickies/jobs.py`, `src/flickies/webhooks.py` | In-memory job queue; signed webhook delivery. |
| `src/flickies/auth.py`, `src/flickies/middleware.py` | Bearer auth; request id, rate limit, idempotency. |
| `src/flickies/errors.py` | `CODE_*` constants and `http_error()`. |
| `src/flickies/config.py`, `src/flickies/logging_config.py`, `src/flickies/prefetch.py` | Core config, JSON logging with redaction, boot weight prefetch. |
| `src/flickies/schema/` | Pydantic models generated from `openapi.yaml` (`_generated.py`); not used by the routes. |
| `src/flickies/_vendor/` | Vendored LatentSync 1.5 (Apache-2.0) and Wav2Lip (non-commercial) source. |
| `openapi.yaml` | The REST contract and the source of every generated file. |
| `engines.json` | The engine registry baked into both images. |
| `pkg/clients/go/`, `pkg/clients/python/` | Generated clients (own Go module, own Python package). |
| `api/oapi-codegen-go.yaml` | oapi-codegen config. |
| `Dockerfile`, `Dockerfile.cuda`, `Dockerfile.dev`, `entrypoint.sh` | CPU image, CUDA image, dev image, container startup. |
| `pyproject.toml`, `uv.lock` | Project metadata, light runtime dependencies, the uv `exclude-newer` gate, ruff and pyright settings. |
| `requirements-heavy-*.txt`, `scripts/heavy-deps-*.in` | Compiled ML stacks and their inputs. |
| `scripts/` | `compile_heavy_deps.sh`, `bump_exclude_newer.sh`, `generate_models.sh`, the heavy-deps inputs and overrides. |
| `tests/` | Unit tests; `tests/integration/` holds only an empty `__init__.py`. |
| `docs/` | The documentation site; `README.md` links to it. |
| `.agents/` | Skill, OpenClaw plugin, Claude and Codex plugin manifests, and these rules. |
| `.github/workflows/` | `pipeline.yml` (lint, test, images, badges, release, ClawHub and MCP Registry), `collaborators-only.yml`, `mirror-and-archive.yml`, `issue-pull.yml`. |
| `server.json`, `glama.json` | MCP Registry entry and Glama maintainer claim. |
| `THIRD_PARTY.md`, `LICENSES/` | Vendored components and their license texts. |
| `.github/FUNDING.yml` | Sponsor links. |

## Dev workflow

Every tool runs in the dev container (`Dockerfile.dev`, tag `psyb0t/flickies-dev:latest`) with the repo mounted at `/work`, except the image builds, `make docs` and `make test-integration`, which run on the host. `make help` lists the targets.

| Target | What it does |
| --- | --- |
| `make dev-image` | Builds the dev image (Python 3.12, uv, ruff 0.7.0, pyright, pytest, datamodel-code-generator, openapi-python-client, Go 1.25 and oapi-codegen; no ML stack). Every dev target depends on it. |
| `make shell` | Interactive shell in the dev container (the only target with `-it`). |
| `make lint` | `ruff check src tests`, `ruff format --check src tests`, `pyright src`. |
| `make format` | `ruff format src tests` then `ruff check --fix src tests`. |
| `make test`, `make test-unit` | `pytest tests/ -v` with coverage on `src/flickies`. |
| `make test-unit-cov-gate` | 80% line coverage gate on config, engine base, license gate and registry. |
| `make check` | `lint` then `test`. |
| `make generate`, `generate-models`, `generate-client-go`, `generate-client-python`, `generate-check` | Regenerate from `openapi.yaml`; `generate-check` fails on drift. |
| `make build`, `build-cuda`, `build-all` | Images tagged `v<pyproject version>` and `latest` (`-cuda` suffix). |
| `make run`, `run-cuda` | Build and run on `PORT` (8000) with `~/.flickies-data` as `/data`. |
| `make pkg-add PKG=...`, `pkg-remove`, `pkg-update`, `pkg-upgrade`, `pkg-lock` | Light dependency changes through uv, moving `exclude-newer` first. |
| `make pkg-compile-heavy` | Recompile `requirements-heavy-*.txt` from `scripts/heavy-deps-*.in`. |
| `make docs` | Build `docs/` with GitHub's Pages image into `.testing/docs-site`. |
| `make version` | Prints `v` plus the `pyproject.toml` version. |
| `make clean` | Removes local images and Python caches. |

## Project-specific landmines

- **`make check` gates the images.** The `code` job in `pipeline.yml` runs `make lint` and `make test`, and the image build depends on it, so a lint or test failure on `main` blocks the release. ruff and pyright skip `src/flickies/_vendor/` and `src/flickies/schema/_generated.py` (`pyproject.toml`).
- **`Dockerfile.dev` pins its own copies of the runtime packages** (fastapi, uvicorn, pydantic, python-multipart, python-json-logger) separately from `uv.lock`; a pin change in `pyproject.toml` needs the same change there. It also pre-fetches pyright's node runtime into `/opt/pyright-cache` (`PYRIGHT_PYTHON_CACHE_DIR`), which needs `libatomic1`.
- **`make generate-check` reports drift on a clean tree.** `_generated.py` embeds a generation timestamp, and `openapi-python-client` is unpinned in `Dockerfile.dev`, so a newer release rewrites the Python client (for example `httpx` imports). Pin the generator before relying on that target.
- **The server does not validate bodies against `openapi.yaml`.** Routes take `body: dict[str, Any]`; a missing required key (`start_sec`, `width`, `rows`) raises `KeyError` and returns a plain-text 500. The generated Pydantic models in `src/flickies/schema/` are not wired in.
- **`/v1/mcp` redirects.** The Starlette mount answers at `/v1/mcp/`; a POST to `/v1/mcp` (the URL in `server.json` and the bridge plugin) gets a 307. There is no rewrite middleware like talkies' `_MCPSlashRewriteMiddleware`.
- **A POST without `Content-Type: application/json` returns a plain-text 500**, not the JSON envelope; invalid JSON with the header is 422 `VALIDATION_FAILED`.
- **Spec and code disagree in places.** REST lipsync ignores `restore_face` (only the MCP tool honours it); `replace_existing_audio` has no effect in `FFmpeg.mux_audio`; `gif_options.palette_mode` is ignored; async jobs ignore `output_path`/`output_url` and always stage to `jobs/`; the staged file name uses a different UUID from `job_id`.
- **Generated clients drop request fields.** `allOf` plus sibling `properties` collapses to the base schema: the Go client loses every endpoint-specific field, the Python client loses them for lipsync, concat, mux audio, extract audio and thumbnail grid. `docs/clients.md` documents the workaround.
- **`pyproject.toml` version lags the releases.** It says `0.3.1` while tags reach `v0.3.17`; releases have bumped `.agents/.codex-plugin/plugin.json` instead. `make version`, `make build` tags and `/v1/health` `version` all read `pyproject.toml`.
- **Wav2Lip downloads the whole LatentSync repo.** The S3FD detector comes from `ByteDance/LatentSync-1.5` `auxiliary/`, and every `snapshot_download` pulls a full repository (no `allow_patterns`).
- **LatentSync is CUDA-image only.** Its libraries are only in `scripts/heavy-deps-cuda.in`; on the CPU image `LatentSync._load_sync` fails on import with a plain 500. GFPGAN is installed in both images and is not `cuda_only`.
- **basicsr needs a source patch.** Both Dockerfiles and `entrypoint.sh` rewrite the `torchvision.transforms.functional_tensor` import in `basicsr/data/degradations.py`; keep the patch while torchvision is 0.17 or newer.
- **Images run as root** and have no `HEALTHCHECK`. Files created in the bind mount are root-owned.
- **`entrypoint.sh` creates `/data/uploads`, which nothing uses.** The staging area is `/data/files` (`files_dir()`).
- **`make test-integration` has no suite.** The Makefile comments describe a pytest harness and `tests/integration/conftest.py`, but `tests/integration/` holds only `__init__.py`.
- **Weights never enter git.** `.gitignore` excludes `*.pt`, `*.pth`, `*.safetensors`, `*.bin`, `*.onnx`, `/models/`, `/data/` and the e2e cache.
- **Untracked local state.** `.research_files/`, `.anustimes/`, `.refactor/`, `.telemetry/`, `.coverage` and the Python caches are local and gitignored. `git-update.sh` is the maintainer's local release script, gitignored and not part of the project. `PLAN.md` is gitignored dev notes.
- **Outside pull requests are closed automatically** by `collaborators-only.yml`, which asks for an issue instead. Issues filed on the GitLab and Codeberg mirrors are pulled in by `issue-pull.yml`.

## Common changes

Adding an ffmpeg operation:

1. Add the method to `FFmpeg` in `src/flickies/ffmpeg.py`, running ffmpeg through `_run()` (PY6, SEC6).
2. Add the route in `server.py` through `_ffmpeg_handler()` and the MCP tool in `mcp_server.py` (API3, MCP2).
3. Add the request schema and path to `openapi.yaml`, run `make generate` (API5), and update `docs/api.md`, `docs/mcp.md`, the README box and the skill (DOC2). The MCP tool count changes too (MCP5).

Adding an engine executor:

1. Write `src/flickies/engines/<name>.py` as an `Engine` subclass (ENG2, ENG3) and add it to `_EXECUTOR_MAP` (ENG1).
2. Add its weight download branch to `_prefetch_one()` in `src/flickies/prefetch.py` (ENG4) and its entry to `engines.json`.
3. Add any library to `scripts/heavy-deps-*.in` and run `make pkg-compile-heavy` (ENG7). Update `THIRD_PARTY.md` for vendored code (SEC9) and `docs/engines.md` (DOC2).

Adding a setting: read it where it is used with the existing truthy set or numeric fallback (PY5), and document it in `docs/configuration.md` and `.agents/skills/flickies/references/setup.md` (DOC2).

Releasing: [docs-and-releases.md](.agents/rules/docs-and-releases.md). Never commit, tag, push or publish unless the user asked for that specific action.

## Rules

Rules for every change: `.agents/rules/`. Read the area file before touching that area:

| File | Read before touching |
| --- | --- |
| `python-code.md` | Any `src/flickies/*.py` outside `_vendor/`, `pyproject.toml` |
| `api-design.md` | `src/flickies/server.py`, `errors.py`, `files.py`, `fetch.py`, `jobs.py`, `webhooks.py`, `middleware.py`, `openapi.yaml`, `pkg/clients/` |
| `engines.md` | `src/flickies/engines/`, `prefetch.py`, `engines.json`, `src/flickies/_vendor/`, the Dockerfiles, `entrypoint.sh`, `requirements-heavy-*.txt`, `scripts/heavy-deps-*.in`, `uv.lock` |
| `mcp.md` | `src/flickies/mcp_server.py`, `.agents/plugins/flickies/`, `server.json` |
| `security.md` | `src/flickies/auth.py`, `files.py`, `fetch.py`, `webhooks.py`, `logging_config.py`, Dockerfiles, `.github/workflows/`, `.gitleaks.toml`, `THIRD_PARTY.md` |
| `testing.md` | `tests/`, `Dockerfile.dev`, `Makefile` test targets |
| `docs-and-releases.md` | `README.md`, `docs/`, `CHANGELOG.md`, `.agents/skills/`, plugin manifests, any version field, commits and tags |
