---
title: "Development"
description: "Work on flickies: repository layout, the dev container and Make targets, lint and tests, code generation from openapi.yaml, dependencies, CI and releases."
nav_order: 12
---

# Development

Everything except the image builds runs inside a dev container, so the host needs only Docker and Make. `make help` lists every target.

## Layout

| Path | What it holds |
| --- | --- |
| [src/flickies/server.py](https://github.com/psyb0t/docker-flickies/blob/main/src/flickies/server.py) | The FastAPI app, every route, the input/output contract, async job scheduling, error handlers. |
| `src/flickies/mcp_server.py` | The FastMCP server mounted at `/v1/mcp`. |
| `src/flickies/engines/` | `base.py` (the engine lifecycle), `_registry.py` (hot-swap and idle unload), `_license_gate.py`, and one module per executor: `wav2lip.py`, `latentsync.py`, `gfpgan.py`. |
| `src/flickies/ffmpeg.py` | Every ffmpeg and ffprobe call. |
| `src/flickies/files.py`, `fetch.py` | Staging-area paths and uploads; URL downloads, presigned PUTs and the private address guard. |
| `src/flickies/jobs.py`, `webhooks.py` | In-memory async jobs; signed webhook delivery with retries. |
| `src/flickies/auth.py`, `middleware.py` | Bearer auth; request ids, rate limit, idempotency. |
| `src/flickies/config.py`, `logging_config.py`, `prefetch.py` | Startup settings, JSON logging, the boot weight download. |
| `src/flickies/schema/` | Pydantic models generated from `openapi.yaml`. The routes do not use them; request bodies are plain dicts. |
| `src/flickies/_vendor/` | Vendored LatentSync 1.5 and Wav2Lip source. See [THIRD_PARTY.md](https://github.com/psyb0t/docker-flickies/blob/main/THIRD_PARTY.md). |
| [openapi.yaml](https://github.com/psyb0t/docker-flickies/blob/main/openapi.yaml) | The REST contract. |
| `engines.json` | The engine registry baked into the images. |
| `pkg/clients/go/`, `pkg/clients/python/` | Generated clients ([Generated clients](clients.md)). |
| `Dockerfile`, `Dockerfile.cuda`, `Dockerfile.dev`, `entrypoint.sh` | CPU image, CUDA image, dev image, container startup. |
| `scripts/` | Dependency compilation, the `exclude-newer` bump and model generation. |
| `tests/` | Unit tests. |
| `docs/` | This site. |
| `.agents/` | The agent skill, the OpenClaw plugin and the Claude Code and Codex plugin manifests. |

## Make targets

| Target | What it does |
| --- | --- |
| `make dev-image` | Builds `psyb0t/flickies-dev:latest` from `Dockerfile.dev`: Python 3.12, uv, ruff, pyright, pytest, the generators and Go. Every dev target depends on it. |
| `make shell` | Interactive shell in the dev container. |
| `make lint` | `ruff check src tests`, `ruff format --check src tests`, `pyright src`. |
| `make format` | `ruff format` then `ruff check --fix`. |
| `make test`, `make test-unit` | `pytest tests/` with coverage. |
| `make test-unit-cov-gate` | Fails below 80% line coverage on the config, engine base, license gate and registry modules. |
| `make check` | `lint` then `test`. |
| `make build`, `make build-cuda`, `make build-all` | Builds the CPU and CUDA images, tagged `v<version>` and `latest` (with `-cuda`). |
| `make run`, `make run-cuda` | Builds and runs an image on `PORT` (default 8000) with `~/.flickies-data` as `/data`. |
| `make docs` | Builds this site with GitHub's Pages image into `.testing/docs-site`. |
| `make version` | Prints `v` and the version in `pyproject.toml`. |
| `make clean` | Removes the local images and Python caches. |

## Tests

Unit tests run offline in the dev image, which has no ML stack. They exercise routing, the error envelope, auth, file staging, jobs, the middleware and the license gate, and run real ffmpeg for `info` and `trim` (skipped if ffmpeg is missing). Engine inference is not covered.

`make test-integration` runs pytest on `tests/integration/` on the host. That directory holds only an empty package today, so there is no integration suite.

## Code generation

`openapi.yaml` is the source for the server models and both clients, and the generated files are committed:

```bash
make generate                # all three
make generate-models         # src/flickies/schema/_generated.py
make generate-client-go      # pkg/clients/go/client.gen.go
make generate-client-python  # pkg/clients/python/flickies-client/
make generate-check          # fails if the generated files differ from git
```

Never edit generated files. Change `openapi.yaml`, run `make generate`, and commit the spec and the output together.

## Dependencies

Light runtime dependencies are in `pyproject.toml` and `uv.lock`. Change them only through `make pkg-add PKG=...`, `pkg-remove`, `pkg-update` or `pkg-upgrade`, which first move the `exclude-newer` date in `pyproject.toml` to seven days ago so the resolver never sees a release younger than a week.

The ML stack (torch, OpenCV, librosa, GFPGAN and, for CUDA, the LatentSync libraries) lives in `scripts/heavy-deps-cpu.in` and `scripts/heavy-deps-cuda.in`. `make pkg-compile-heavy` compiles them into `requirements-heavy-cpu.txt` and `requirements-heavy-cuda.txt`, which the Dockerfiles install.

## CI and releases

[.github/workflows/pipeline.yml](https://github.com/psyb0t/docker-flickies/blob/main/.github/workflows/pipeline.yml) runs on every push:

- every branch: `make lint` and `make test`;
- the default branch, after those pass: build, scan and push both images as `latest` and `sha-<commit>` (each with `-cuda` for the CUDA image), and refresh the README badges;
- a `v*` tag: wait for that commit's default-branch run to succeed, re-tag the same images as `vX.Y.Z` and `vX.Y.Z-cuda` without rebuilding, create the GitHub release, publish the skill and plugin to ClawHub, and publish `server.json` to the MCP Registry.

A tag therefore only releases a commit that is already on the default branch with a green pipeline. Other workflows close outside pull requests (`collaborators-only.yml`), mirror and archive the repository (`mirror-and-archive.yml`), and copy issues back from the mirrors (`issue-pull.yml`).

Changes are listed in [CHANGELOG.md](https://github.com/psyb0t/docker-flickies/blob/main/CHANGELOG.md).
