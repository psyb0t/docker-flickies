---
title: "Security"
description: "What a flickies server can reach and store, the bearer token, URL fetch guard, rate limit and path checks, and what to set before exposing it."
nav_order: 10
---

# Security

flickies is built for one operator on a trusted host. It has one shared token, no users, and one staging area that every caller can read and write. Read this page before the port leaves your machine.

## Before you expose it

1. Set `FLICKIES_AUTH_TOKEN` to a long random value, for example `openssl rand -hex 32`.
2. Publish the port on loopback (`-p 127.0.0.1:8000:8000`) and put a reverse proxy with TLS in front if other machines need it.
3. Leave `FLICKIES_ALLOW_PRIVATE_FETCH` off.
4. Set `FLICKIES_WEBHOOK_SECRET` if you use webhooks, and verify the signature on the receiving side.

## Authentication

Without `FLICKIES_AUTH_TOKEN` there is no authentication: anyone who can reach the port can upload, download and delete staged files, evict engines and run jobs, over REST and MCP alike. The entrypoint prints `bearer auth DISABLED` at startup in that case.

With the token set, every request needs `Authorization: Bearer <token>`. The check is ASGI middleware ([src/flickies/auth.py](https://github.com/psyb0t/docker-flickies/blob/main/src/flickies/auth.py)) in front of every route and the `/v1/mcp` mount, and compares in constant time. Only `/healthz` and CORS `OPTIONS` preflights pass without it; `/v1/health` needs it too. A missing or wrong token gets 401 with `WWW-Authenticate: Bearer`.

The token is all or nothing. Anyone holding it can delete any staged file or evict the engine another caller is using.

## What it can reach

- **The network, for `file_url` and `output_url`.** Only `http` and `https`. The server resolves the host and refuses private, loopback, link-local, multicast and reserved addresses unless `FLICKIES_ALLOW_PRIVATE_FETCH` is on. The check runs on the URL you send; downloads follow redirects without checking the new address. Downloads have no size cap, only the `FLICKIES_FETCH_TIMEOUT_SECS` timeout.
- **The network, for `webhook_url`.** Webhook URLs are not checked at all, so a caller can make the server POST job results to any address it can reach, including private ones.
- **Hugging Face**, to download model weights, unless `FLICKIES_OFFLINE=1`.
- **The GPU**, through the CUDA image.

## What it stores

- Staged inputs, outputs and async job results under `/data/files`, kept until deleted. Nothing expires.
- Model weights under `/data/hf` and `/data/models`.
- Logs under `/data/logs`, with secrets redacted and URL query strings removed ([Logging](logging.md#redaction)).
- In memory only: async job state, the idempotency cache and rate-limit counters. All of it is lost on restart.

## Limits and checks

| Check | Behaviour |
| --- | --- |
| Paths | Every staged path is resolved under `/data/files`. Empty, absolute, `..`, NUL bytes or anything that resolves outside it is 400 ([src/flickies/files.py](https://github.com/psyb0t/docker-flickies/blob/main/src/flickies/files.py)). |
| Upload size | `PUT /v1/files/{path}` stops at `FLICKIES_MAX_UPLOAD_BYTES` (5 GiB) with 413. |
| Rate limit | `FLICKIES_RATE_LIMIT_PER_MIN` per client IP. The IP is the first `X-Forwarded-For` value when that header is present, so a client that reaches the server directly can pick its own IP. Only trust it behind a proxy that sets the header. |
| Idempotency | `Idempotency-Key` responses are cached by key, method and path, not by caller. Two callers using the same key on the same route share a response. |
| Subprocesses | ffmpeg and ffprobe run with an argument list, never through a shell. There is no timeout on them. |
| Error details | `FFMPEG_FAILED` responses include the ffmpeg command line, with server-side file paths, and the end of its stderr. |

## Licenses

The Wav2Lip engines and the vendored Wav2Lip source are for non-commercial use only. The non-commercial gate stops the engines from loading, but the code is in every image. See [Engines](engines.md#licenses).

## Reporting a problem

Pull requests from outside are closed automatically. Open an [issue](https://github.com/psyb0t/docker-flickies/issues) instead.
