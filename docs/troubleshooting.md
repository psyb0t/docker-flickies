---
title: "Troubleshooting"
description: "flickies errors with their exact messages, causes and fixes: the non-commercial gate, CUDA-only LatentSync, file paths, URL fetches, ffmpeg and jobs."
nav_order: 11
---

# Troubleshooting

Each entry gives the message you see, why it happens and what to do. Most messages come back in the JSON `message` field; the [error table](api.md#errors) lists the codes. The logs usually say more ([Logging](logging.md)).

## Startup

### `engines file not found: /app/engines.json`

`FLICKIES_ENGINES_FILE` points at a file that does not exist, often a mount with a typo in the host path. The server exits. Fix the path or remove the variable.

### `FLICKIES_PORT not an int` or `FLICKIES_PORT out of range`

The port must be an integer from 1 to 65535.

### `[flickies.logging] file handler disabled: path=... err=...`

The log file could not be opened, usually because `/data` is read-only or not writable. The server keeps logging to stderr.

## Engines

### 403 `NONCOMMERCIAL_GATE_REFUSED`

`wav2lip: non-commercial opt-in missing. Set FLICKIES_ENABLE_NONCOMMERCIAL=1 in the server environment to load this engine. ...`

The Wav2Lip engines need the opt-in on the server. Restart the container with `-e FLICKIES_ENABLE_NONCOMMERCIAL=1`, if your use allows it, or use `latentsync-1.5` on the CUDA image.

### 400 `latentsync-1.5 is CUDA-only; FLICKIES_DEVICE=cuda required.`

The CUDA image started without a visible GPU. Add `--gpus all` and check the NVIDIA Container Toolkit with `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`.

### Plain-text `500 Internal Server Error` from lipsync on the CPU image

LatentSync 1.5 is the default engine and its libraries are not in the CPU image. Pass `"engine": "wav2lip"` (with the opt-in) or use the CUDA image.

### 404 `ENGINE_NOT_REGISTERED`

The slug is not in the registry. `GET /v1/engines` lists the valid ones. With a custom `engines.json`, an entry with an unknown `executor` is skipped at startup with an `engine skipped` warning (`reason: unknown_executor`) in the log.

### 400 `Wav2Lip repo Nekochu/Wav2Lip unavailable: ...`, `GFPGAN repo leonelhs/gfpgan unavailable: ...` or `LatentSync weights unavailable: ...`

The weights could not be downloaded, or `FLICKIES_OFFLINE=1` is set and they are not staged. Check that the container can reach huggingface.co, or stage the files as described in [Deployment](deployment.md#offline-hosts). The Wav2Lip face detector download is not wrapped this way; when it fails you get a plain-text 500 and the cause in the logs.

### The first request takes minutes

The engine is downloading its whole Hugging Face repository. Later requests reuse `/data/hf`. Prefetch at boot with `FLICKIES_ENABLED_ENGINES` to move the wait to startup.

### Every other request is slow

Each request for a different engine unloads the current one and loads the new one ([Engines](engines.md#one-engine-at-a-time)). Group requests by engine, or run a second container.

## Files and paths

### 400 `must provide exactly one of: file_path, file_url`

Send exactly one input. The same rule applies to `face_path`/`face_url` and `audio_path`/`audio_url` on lipsync.

### 400 `video-producing endpoint requires output_path or output_url (or set async_job=true)`

Add `output_path` or `output_url`, or set `async_job: true`.

### 400 `output_path and output_url are mutually exclusive`

Send only one of them.

### 400 `parent-directory components not allowed`, `absolute paths not allowed`, `path escapes files dir`

Paths are relative to the staging area, `/data/files`. Write `uploads/clip.mp4`, not `/data/files/uploads/clip.mp4`.

### 500 `FFMPEG_FAILED` with `No such file or directory` in `details.stderr`

The staged file does not exist. Paths are not checked for existence before ffmpeg runs. Upload it first, or check the spelling against the host directory `$HOME/flickies-data/files`.

### 413 `upload exceeded 5368709120 bytes`

The upload is larger than `FLICKIES_MAX_UPLOAD_BYTES`. Raise the limit or pass a `file_url` instead.

## URLs

### 400 `URL resolves to private/loopback IP (...); set FLICKIES_ALLOW_PRIVATE_FETCH=1 to permit`

The `file_url` or `output_url` host points at a private address, for example another container on the same machine. Set `FLICKIES_ALLOW_PRIVATE_FETCH=1` if you trust every caller, or serve the file from a public address.

### 400 `unsupported URL scheme: ...`

Only `http` and `https` URLs work.

### 502 `UPSTREAM_FETCH_FAILED`

`upstream GET <url> returned <status>` or `upstream PUT <url> returned <status>`: the remote server answered with an error. For a presigned `output_url`, check that it allows PUT and has not expired. A transport error (timeout, refused connection) gives the httpx message instead.

## ffmpeg operations

### 400 `end_sec must be > start_sec`

Swap or fix the trim boundaries.

### Trim starts a few seconds late

Without `precise`, trim copies streams and the start snaps to a keyframe. Send `"precise": true`.

### Concat output is corrupt or concat fails

The inputs differ in codec, timebase or sample aspect ratio. Send `"precise": true` to re-encode them.

### 400 `concat needs >= 2 inputs` or `exactly one of inputs_paths / inputs_urls required`

Send two or more inputs in one of the two lists.

### Plain-text `500 Internal Server Error` from trim, scale or thumbnail grid

A required field is missing (`start_sec`/`end_sec`, `width`/`height`, `rows`/`cols`). The server does not validate bodies against the spec, so the missing key crashes the handler.

### Plain-text `500 Internal Server Error` from any POST

The request has no `Content-Type: application/json` header. curl's `-d` alone sends a form content type; add `-H "Content-Type: application/json"`.

### The thumbnail grid only shows the start of the video

The grid takes one frame from each run of 100 frames, so a 3 x 4 grid covers the first 1,200 frames. See [thumbnail grid](api.md#post-v1videothumbnail_grid).

## Jobs and webhooks

### 404 `job not found: ...`

The id is wrong or the server restarted. Jobs live in memory. A finished job's file is still in `/data/files/jobs/`.

### The job finished but the file is not at `jobs/<job_id>.mp4`

The file name under `jobs/` is a different UUID. Read `result.path` from `GET /v1/jobs/{job_id}`.

### `error.code` is `JOB_FAILED`

The job raised an error; `error.message` carries the original text. Look up that text on this page.

### The webhook never arrives

Look for `webhook non-2xx`, `webhook transport error` and `webhook dead-letter` in the logs. Retries back off up to 12 hours apart, so a receiver that was down may still get the delivery later, unless the server restarted.

## Requests rejected

### 401 `missing Authorization: Bearer header` or `invalid bearer token`

Auth is on. Send `Authorization: Bearer <token>`. `/v1/health` needs the token too; only `/healthz` is open.

### 429 `RATE_LIMITED`

More than `FLICKIES_RATE_LIMIT_PER_MIN` requests a minute from one IP. Polling a job in a tight loop is the usual cause. Poll less often or raise the limit; `0` turns it off.

### 422 `VALIDATION_FAILED`

The body is not valid JSON, or not a JSON object. Check the quoting in your shell.
