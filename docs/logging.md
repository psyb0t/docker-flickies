---
title: "Logging"
description: "flickies logs JSON to stderr and a rotating file: the fields on every line, request and trace ids, secret redaction, and what DEBUG records."
nav_order: 9
---

# Logging

flickies writes structured JSON to stderr (so `docker logs` shows it) and to a rotating file at the same time. The setup is in [src/flickies/logging_config.py](https://github.com/psyb0t/docker-flickies/blob/main/src/flickies/logging_config.py).

## Where

| Output | Details |
| --- | --- |
| stderr | Every line, always. |
| `FLICKIES_LOG_FILE` | Default `/data/logs/flickies.log`. Rotates at 50 MB and keeps 5 old files. If the file cannot be opened, the server logs to stderr only and prints `[flickies.logging] file handler disabled: path=... err=...`. |

uvicorn's own logs (startup, access lines) go through the same handlers and format.

The entrypoint prints a few plain-text lines before the server starts: whether bearer auth is on, whether the non-commercial gate is open, and a note if the boot prefetch failed.

## Fields

Every line has:

| Field | Meaning |
| --- | --- |
| `time` | ISO 8601 UTC with milliseconds, for example `2026-11-09T10:15:42.317Z`. |
| `level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `logger` | `flickies.server`, `flickies.ffmpeg`, `flickies.fetch`, `flickies.jobs`, `flickies.webhooks` and so on. |
| `file`, `line`, `func` | Where the line was logged. |
| `msg` | The message, such as `request rejected` or `hot-swap eviction`. |
| `trace_id`, `request_id` | Request correlation ids (empty outside a request). |

Other fields depend on the line: `engine_slug`, `job_id`, `path`, `status`, `code`, `wall_secs`, `size`, and on warnings a `reason` such as `client_error`, `ssrf_private_ip`, `bucket_empty` or `noncommercial_gate_refused`. Prefetch lines carry `component: prefetch`.

## Tracing a request

The server takes `X-Request-Id` from the request if it is a UUID or a ULID, otherwise it makes a UUID4. `X-Trace-Id` gets the same treatment and falls back to the request id. Both go on every log line of that request, back to the caller as response headers, and onward on `file_url` downloads and `output_url` uploads, so the next service can log the same ids. Send your own ids to find a request in the logs:

```bash
curl -s -X POST http://localhost:8000/v1/video/info \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: 2b7f3c1e-8d4a-4f6b-9a2e-5c1d0e9f7a3b" \
  -d '{"file_path": "uploads/clip.mp4"}'

docker logs flickies 2>&1 | grep 2b7f3c1e-8d4a-4f6b-9a2e-5c1d0e9f7a3b
```

Async jobs log with the `job_id` field.

## Redaction

Before a line is written, any key or string value matching `password`, `token`, `secret`, `api_key`, `authorization`, `cookie`, `set-cookie`, `x-api-key`, a Hugging Face token (`hf_...`) or an API key starting with `sk-` or `sk-ant-` is replaced with `[REDACTED]`. The match is a substring, so a value that merely contains the word `token` is redacted whole.

Logged URLs have their query string removed, so presigned URL signatures never reach the logs.

## DEBUG

`FLICKIES_LOG_LEVEL=DEBUG` records enough to reconstruct what happened:

- every ffmpeg and ffprobe command line and its result;
- which path trim and concat took (`stream_copy` or `precise_reencode`) and how transcode ran (`gif_palette_two_pass` or `standard_reencode`);
- engine inference start, end, output size and `wall_secs`;
- URL download and upload byte counts;
- job submit, start, completion and cancel decisions;
- where each output was written.

At `INFO` you get startup, engine loads and evictions, job completions, webhook deliveries and every rejected request (4xx as `WARNING`, 5xx as `ERROR`).
