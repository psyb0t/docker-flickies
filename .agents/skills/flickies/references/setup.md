# flickies setup

## Requirements

- Docker
- Optional: NVIDIA GPU + NVIDIA Container Toolkit for the CUDA image (required for `latentsync-1.5` and `gfpgan`; Wav2Lip runs on CPU too, slowly)
- A bind-mounted `/data` volume for model weights + staged files (weights live in the standard HuggingFace cache layout and are reusable across containers)
- Tested GPU ceiling: **RTX 3060 12 GB** — fits LatentSync 1.5 (~8 GB) with headroom; the Wav2Lip + GFPGAN chain peaks at ~5 GB. One engine resident at a time.

## Quick Install

### CPU

Runs every ffmpeg op (trim / concat / transcode incl. gif / scale / mux / extract / thumbnail-grid / info) plus Wav2Lip-CPU (~44s for a 3s clip — fine for short clips, and only when the non-commercial gate is set). GFPGAN and LatentSync 1.5 are CUDA-only — the CPU image refuses to load them.

```bash
docker run -d --name flickies \
  -v $HOME/flickies-data:/data \
  -p 8000:8000 \
  psyb0t/flickies:latest
```

### CUDA

Runs every engine at usable speed (LatentSync 1.5, Wav2Lip / Wav2Lip-GAN, GFPGAN) plus all ffmpeg ops. Requires the NVIDIA Container Toolkit on the host.

```bash
docker run -d --name flickies \
  --gpus all \
  -v $HOME/flickies-data:/data \
  -p 8000:8000 \
  psyb0t/flickies:latest-cuda
```

Both images `EXPOSE 8000` and bind `0.0.0.0:8000` inside the container (the entrypoint forces `FLICKIES_HOST=0.0.0.0`). Control network exposure at `docker run` time with `-p` (see [Ports](#ports)).

**Verify:** `curl http://localhost:8000/healthz` returns `{"status": "ok"}` once boot is done. `curl http://localhost:8000/v1/health | jq` gives the richer discovery payload (device, ffmpeg version, available/enabled/loaded engines, non-commercial flag).

### Enable the non-commercial engines (Wav2Lip)

Wav2Lip / Wav2Lip-GAN are trained on LRS2 (non-commercial). The server refuses to load them unless `FLICKIES_ENABLE_NONCOMMERCIAL=1` is set. LatentSync 1.5 (Apache-2.0) is the commercial-safe default and needs no gate.

```bash
docker run -d --name flickies \
  --gpus all \
  -e FLICKIES_ENABLE_NONCOMMERCIAL=1 \
  -v $HOME/flickies-data:/data \
  -p 8000:8000 \
  psyb0t/flickies:latest-cuda
```

## Model Weights

Weights live in the standard HuggingFace cache layout under `/data/hf/hub/models--<org>--<name>/…` (content-addressed blobs + snapshot symlinks), reusable by any HF-aware tool sharing the bind mount.

| engine | HF repo | license | gate |
|---|---|---|---|
| `latentsync-1.5` | `ByteDance/LatentSync-1.5` | Apache-2.0 | none (CUDA-only) |
| `wav2lip` / `wav2lip-gan` | `Nekochu/Wav2Lip` | LRS2 non-commercial | `FLICKIES_ENABLE_NONCOMMERCIAL=1` |
| `gfpgan` | `leonelhs/gfpgan` | Apache-2.0 | none (CUDA-only) |
| S3FD detector | `ByteDance/LatentSync-1.5` (bundled) | — | — |

**Lazy by default** — each engine fetches its repo on first request. To pull at boot before the server accepts requests, set `FLICKIES_ENABLED_ENGINES=wav2lip,gfpgan` (prefetch just those) or `FLICKIES_PREFETCH_ALL=1` (prefetch all; CUDA engines pulled only when the device is CUDA). `FLICKIES_OFFLINE=1` skips auto-download entirely (operator stages the snapshot dir manually).

## Environment Variables

All server-side (set at `docker run` time). Everything defaults sensibly; the two you'll actually touch are `FLICKIES_AUTH_TOKEN` and `FLICKIES_ENABLE_NONCOMMERCIAL`.

### Core

| Var | Default | What it does |
|---|---|---|
| `FLICKIES_AUTH_TOKEN` | (empty = no auth) | Bearer token required on every route except `/healthz`. Empty/unset = wide open: the API/MCP surface is unauthenticated and anyone who can reach the port gets full access. When set, `Authorization: Bearer <token>` is required on every HTTP request and MCP call. Set it for any deployment beyond localhost, and bind to loopback / behind an authenticating proxy. See [Security & safety](../SKILL.md#security--safety) in the skill doc. |
| `FLICKIES_ENABLE_NONCOMMERCIAL` | (unset = refuse) | Set to `1` / `true` / `yes` / `on` to allow the `wav2lip` / `wav2lip-gan` engines to load (LRS2 non-commercial training data). Unset → those slugs return 403 `NONCOMMERCIAL_GATE_REFUSED`. |
| `FLICKIES_DEVICE` | `auto` | `auto` picks `cuda` if available else `cpu`. Also `cpu` / `cuda`. |
| `FLICKIES_DATA_DIR` | `/data` | Base data dir. Staged files → `<data>/uploads` + FILES_DIR; model snapshots → `<data>/hf` cache; async job outputs → `<data>/jobs/`. Bind-mount to persist across restarts. |

### Engines + prefetch

| Var | Default | What it does |
|---|---|---|
| `FLICKIES_ENGINES_FILE` | `/app/engines.json` | Path to the engine registry JSON. Override to ship a custom subset. |
| `FLICKIES_ENABLED_ENGINES` | (empty = all, lazy) | Comma-separated engine slug whitelist to prefetch at boot. Empty → download lazily on first request. |
| `FLICKIES_PREFETCH_ALL` | (unset) | `1` → prefetch every engine in `engines.json` at boot (CUDA engines only when the device is CUDA). |
| `FLICKIES_OFFLINE` | (unset) | `1` → skip prefetch; weights must be staged manually. |
| `FLICKIES_IDLE_UNLOAD_SECS` | `600` | Idle seconds before the background sweeper unloads a resident engine from VRAM. Set high to keep a model warm. |

### Webhooks

| Var | Default | What it does |
|---|---|---|
| `FLICKIES_WEBHOOK_SECRET` | (empty) | HMAC-SHA256 signing key for async-completion webhooks. When set, `X-Webhook-Signature: t=<ts>,v1=<hex>` is computed over `timestamp + "." + body`; empty → signature header sent empty. Receivers verify with this shared secret. |

### Logging

| Var | Default | What it does |
|---|---|---|
| `FLICKIES_LOG_LEVEL` | `INFO` | `DEBUG` gives reconstruction-grade tracing (every ffmpeg/ffprobe command + result, engine timing, job lifecycle). |
| `FLICKIES_LOG_FILE` | `<data>/logs/flickies.log` | Rotating JSON log file (in addition to stderr). |

### Bind (usually leave alone)

| Var | Default | What it does |
|---|---|---|
| `FLICKIES_HOST` | `0.0.0.0` (forced by entrypoint) | Bind address inside the container. Control external exposure via `-p` at `docker run` time, not this. |
| `FLICKIES_PORT` | `8000` | Bind port inside the container. |

### HuggingFace token (private repos only)

`HF_TOKEN` / `HUGGINGFACE_TOKEN` are aliased to each other by the entrypoint. Set one if any engine repo is private. `TORCH_HOME` defaults to `<data>/torch_cache`.

## Ports

| Port | Service |
| ---- | ------- |
| 8000 | HTTP REST API + MCP (`/v1/mcp`) on the same port |

The container binds `0.0.0.0:8000` unconditionally. Use `-p` at `docker run` time:

- `-p 127.0.0.1:8000:8000` — loopback-only on the host.
- `-p 8000:8000` — all host interfaces.
- For untrusted networks, combine `FLICKIES_AUTH_TOKEN` with a reverse proxy doing TLS + rate limiting.

## Common Configurations

```bash
# Bearer auth + non-commercial engines on a CUDA host.
docker run -d --name flickies --gpus all -p 8000:8000 \
  -e FLICKIES_AUTH_TOKEN=$(openssl rand -hex 32) \
  -e FLICKIES_ENABLE_NONCOMMERCIAL=1 \
  -v $HOME/flickies-data:/data \
  psyb0t/flickies:latest-cuda

# Prefetch weights at boot so the first request doesn't pay the download tax.
docker run -d --name flickies --gpus all -p 8000:8000 \
  -e FLICKIES_ENABLED_ENGINES=latentsync-1.5,gfpgan \
  -v $HOME/flickies-data:/data \
  psyb0t/flickies:latest-cuda

# Keep a model resident forever (disable idle unload).
docker run -d --name flickies --gpus all -p 8000:8000 \
  -e FLICKIES_IDLE_UNLOAD_SECS=999999999 \
  -v $HOME/flickies-data:/data \
  psyb0t/flickies:latest-cuda

# Webhooks: sign async-completion callbacks.
docker run -d --name flickies --gpus all -p 8000:8000 \
  -e FLICKIES_WEBHOOK_SECRET=$(openssl rand -hex 32) \
  -v $HOME/flickies-data:/data \
  psyb0t/flickies:latest-cuda

# Loopback only (rely on a reverse proxy for external access).
docker run -d --name flickies -p 127.0.0.1:8000:8000 \
  -v $HOME/flickies-data:/data \
  psyb0t/flickies:latest
```

## Custom Engine Registry

The image ships `engines.json` baked at `/app/engines.json`. Override without rebuilding by bind-mounting your own or pointing `FLICKIES_ENGINES_FILE` at a different path inside the container:

```bash
docker run -d --name flickies --gpus all -p 8000:8000 \
  -v $HOME/flickies-data:/data \
  -v $PWD/my-engines.json:/app/engines.json:ro \
  psyb0t/flickies:latest-cuda
```

Each engine entry carries `executor`, optional `variant`, `weights_file`, `cuda_only`, `noncommercial`, `vram_gb_min`, and `description`.

## Management

```bash
docker logs -f flickies                  # tail logs
docker stop flickies                     # stop
docker rm flickies                       # remove
docker pull psyb0t/flickies:latest       # update (CPU)
docker pull psyb0t/flickies:latest-cuda  # update (CUDA)
```

Inspect + control resident engines over the API:

```bash
curl -s http://localhost:8000/v1/engines | jq              # list + load state + idle age
curl -s -X DELETE http://localhost:8000/v1/engines/latentsync-1.5   # evict a resident engine from VRAM (204)
```

Engine eviction and staged-file removal are state-changing operations — run them only against a resource the current task created, and only when the user asked. On a shared instance, evicting an engine can interrupt another caller who is mid-request with it.

## OpenClaw / ClawHub Config

```bash
export FLICKIES_URL=http://localhost:8000
export FLICKIES_AUTH_TOKEN=<token>  # only if the server requires it
```

Or via `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "flickies": {
        "env": {
          "FLICKIES_URL": "http://localhost:8000",
          "FLICKIES_AUTH_TOKEN": "<token>"
        }
      }
    }
  }
}
```

The skill talks to an instance the operator already runs. It never provisions, installs, or escalates on the caller's machine — it only sends requests to `FLICKIES_URL`.
