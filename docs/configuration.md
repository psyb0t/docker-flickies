---
title: "Configuration"
description: "Every flickies environment variable with its default: auth, device, engines and prefetch, limits, URL fetching, webhooks, logging and bind address."
nav_order: 4
---

# Configuration

flickies reads its settings from environment variables, set with `-e` on `docker run`. Every one is read at startup, so a change needs a container restart. Nothing is required: with no variables set you get an open server on port 8000 that downloads models on demand.

Boolean settings are on when the value is `1`, `true`, `yes` or `on` (any case). Anything else, including empty, is off.

## Access

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_AUTH_TOKEN` | empty | Bearer token for every route except `/healthz`. Empty means no auth at all. See [Security](security.md#authentication). |
| `FLICKIES_ENABLE_NONCOMMERCIAL` | off | Lets the `wav2lip` and `wav2lip-gan` engines load. Off, they answer 403 `NONCOMMERCIAL_GATE_REFUSED`. See [Engines](engines.md#licenses). |

## Device and engines

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_DEVICE` | `auto` | `auto` uses CUDA when torch sees a GPU, else the CPU. `cpu` and `cuda` force it. LatentSync 1.5 needs CUDA whatever this says. |
| `FLICKIES_ENGINES_FILE` | `/app/engines.json` | The engine registry. The server refuses to start if the file is missing. |
| `FLICKIES_ENABLED_ENGINES` | empty | Comma-separated slugs to download at boot. It does not limit which engines can be used. |
| `FLICKIES_PREFETCH_ALL` | off | Download every engine at boot when `FLICKIES_ENABLED_ENGINES` is empty. CUDA-only engines are skipped without a GPU. |
| `FLICKIES_OFFLINE` | off | Skip the boot prefetch and load weights from local files only. See [Deployment](deployment.md#offline-hosts). |
| `FLICKIES_IDLE_UNLOAD_SECS` | `600` | Unload an engine that has been idle this many seconds. |
| `FLICKIES_SWEEP_INTERVAL_SECS` | `30` | How often the idle check runs. |
| `HF_TOKEN`, `HUGGINGFACE_TOKEN` | empty | Hugging Face token for gated or private repositories. The entrypoint copies whichever is set to the other. |

Download progress and failures are in the logs ([Logging](logging.md)).

## Limits

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_MAX_UPLOAD_BYTES` | `5368709120` (5 GiB) | Largest `PUT /v1/files/{path}` body. Bigger uploads get 413 and the partial file is deleted. It does not cap `file_url` downloads. |
| `FLICKIES_RATE_LIMIT_PER_MIN` | `60` | Requests per minute per client IP (token bucket, bursts up to the same number). `0` turns rate limiting off. `/healthz` is exempt. |
| `FLICKIES_IDEMPOTENCY_CACHE_SIZE` | `1024` | How many `Idempotency-Key` responses to remember. `0` turns the cache off. |

A value that is not an integer falls back to the default instead of stopping the server.

## URL inputs and outputs

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_FETCH_TIMEOUT_SECS` | `300` | Timeout in seconds for `file_url` downloads and `output_url` uploads. A value that is not a number stops the server at startup. |
| `FLICKIES_ALLOW_PRIVATE_FETCH` | off | Allow `file_url` and `output_url` hosts that resolve to private, loopback, link-local, multicast or reserved addresses. Off, those are refused with 400. |

## Webhooks

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_WEBHOOK_SECRET` | empty | HMAC-SHA256 key for `X-Webhook-Signature` on async job callbacks. Empty sends the header with an empty `v1=` value. See [REST API](api.md#webhooks). |

## Logging

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. An unknown value means `INFO`. |
| `FLICKIES_LOG_FILE` | `$FLICKIES_DATA_DIR/logs/flickies.log` | Rotating JSON log, written next to stderr. |

## Paths and bind address

| Variable | Default | What it does |
| --- | --- | --- |
| `FLICKIES_DATA_DIR` | `/data` | Root of everything the server keeps. See [Deployment](deployment.md#what-lives-in-data). |
| `FLICKIES_HOST` | `0.0.0.0` | Bind address inside the container. The entrypoint sets this default; running `python -m flickies` outside the image defaults to `127.0.0.1`. |
| `FLICKIES_PORT` | `8000` | Bind port inside the container. Must be 1 to 65535 or the server refuses to start. |
| `TORCH_HOME` | `$FLICKIES_DATA_DIR/torch_cache` | torch's own download cache. |
| `HF_HOME` | `/data/hf` | Hugging Face cache, set in both Dockerfiles. |
