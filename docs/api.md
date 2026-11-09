---
title: "REST API"
description: "Every flickies REST endpoint: the input and output contract, files, jobs, engines, lipsync, restore, ffmpeg ops, webhooks, headers and error codes."
nav_order: 5
---

# REST API

The REST API is the full surface of flickies. Every route is under `/v1/` on port 8000, takes and returns JSON (except file transfers), and is described in [openapi.yaml](https://github.com/psyb0t/docker-flickies/blob/main/openapi.yaml). The same operations are available as [MCP tools](mcp.md).

The server does not validate request bodies against `openapi.yaml`. Each route reads the fields it needs; a missing required field such as `start_sec` on trim or `rows` on thumbnail grid ends in a plain-text `500 Internal Server Error` instead of a JSON error. Send `Content-Type: application/json` on every POST: without it the request also fails with that plain-text 500.

## The contract

Every video endpoint follows the same rules.

**Input**: exactly one of `file_path` (relative to the staging area, `/data/files`) or `file_url` (an `http` or `https` URL the server downloads to a temp file). Both or neither is 400 `must provide exactly one of: file_path, file_url`. Lipsync uses `face_path`/`face_url` and `audio_path`/`audio_url` with the same rule; concat and mux audio have their own fields.

**Output**: exactly one of `output_path` (written into the staging area, parent directories created) or `output_url` (the server PUTs the result there, for example a presigned S3 URL). Both is 400. Neither is 400 unless `async_job` is true.

| Output | Response |
| --- | --- |
| `output_path` | `200 {"path": "<output_path>", "size": <bytes>}` |
| `output_url` | `200 {"url": "<output_url>", "size": <bytes>}` |
| `async_job: true` | `202 {"job_id": "<uuid>", "status": "accepted"}` |

An existing file at `output_path` is overwritten.

**Async jobs**: with `"async_job": true` the work runs in the background and the response is 202 at once. The result always goes to `jobs/<uuid>.<ext>` in the staging area; `output_path` and `output_url` are ignored in async mode (sending both is still rejected). Poll [`GET /v1/jobs/{job_id}`](#get-v1jobsjob_id) or pass `webhook_url` to get called back ([Webhooks](#webhooks)). Lipsync and restore load their engine before queueing the job, so a cold engine still holds the request while it downloads and loads.

Paths are checked before any disk access: empty, absolute, containing `..`, containing a NUL byte, or resolving outside the staging area is 400.

## Health and discovery

### `GET /healthz`

Liveness probe. Always `{"status": "ok"}`, never needs a token, not rate limited.

### `GET /v1/health`

```json
{
  "status": "ok",
  "version": "...",
  "device": "auto",
  "ffmpeg": "ffmpeg version ...",
  "available_engines": ["gfpgan", "latentsync-1.5", "wav2lip", "wav2lip-gan"],
  "enabled_engines": [],
  "loaded_engine": null,
  "noncommercial_enabled": false
}
```

`device` is the `FLICKIES_DEVICE` setting, not the detected device. `enabled_engines` is `FLICKIES_ENABLED_ENGINES`. `ffmpeg` is the first line of `ffmpeg -version`, or null if ffmpeg failed. This route needs the bearer token when auth is on; only `/healthz` is exempt.

## Engines

### `GET /v1/engines`

Lists every registered engine:

```json
{
  "engines": [
    {
      "slug": "wav2lip",
      "executor": "wav2lip",
      "variant": "base",
      "loaded": false,
      "noncommercial": true,
      "cuda_only": false,
      "vram_gb_min": 3,
      "description": "Wav2Lip base ...",
      "last_used_secs_ago": null
    }
  ]
}
```

### `DELETE /v1/engines/{slug}`

Unloads the engine and frees its memory. 204 whether or not it was loaded, 404 `ENGINE_NOT_REGISTERED` for an unknown slug. After this, `loaded_engine` in `/v1/health` can still name the engine until another one loads; `loaded` in `/v1/engines` is the real state. Evicting an engine another caller is using breaks their request.

## Files

The staging area is `/data/files`. There is no listing endpoint.

### `PUT /v1/files/{path}`

Uploads the raw request body (not multipart) to `{path}`, creating directories, overwriting any existing file. 201:

```json
{
  "path": "uploads/clip.mp4",
  "size": 1048576,
  "sha256": "e3b0c442..."
}
```

A body over `FLICKIES_MAX_UPLOAD_BYTES` (5 GiB by default) is 413 `PAYLOAD_TOO_LARGE`, and the partial file is removed.

### `GET /v1/files/{path}`

Streams the file as `application/octet-stream`. 404 `NOT_FOUND` if it does not exist.

### `DELETE /v1/files/{path}`

204 on success, 404 if missing, 400 `refuse to delete a directory` for a directory.

## Jobs

### `GET /v1/jobs/{job_id}`

```json
{
  "job_id": "3f0c2a5e-...",
  "status": "complete",
  "result": {
    "path": "jobs/9b1e7d40-....mp4",
    "size": 2211840
  },
  "error": null
}
```

`status` is `pending`, `running`, `complete` or `failed`. A failed job has `result: null` and `error: {"code": "JOB_FAILED", "message": "..."}`. 404 for an unknown id.

Jobs live in the server's memory: they are lost on restart and never expire while it runs. There is no cancel endpoint. The file name in `result.path` is a different UUID from `job_id`, so read the path from the result.

## Lipsync

### `POST /v1/video/lipsync`

Drives a face video or still image with an audio track.

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `face_path` / `face_url` | one of | | The face. A still image is recognised by a `.jpg`, `.jpeg` or `.png` name (Wav2Lip), so stage images and pass `face_path`. |
| `audio_path` / `audio_url` | one of | | The driving audio, any format ffmpeg reads. |
| `engine` | no | `latentsync-1.5` | `latentsync-1.5`, `wav2lip` or `wav2lip-gan` ([Engines](engines.md)). |
| `output_path` / `output_url` / `async_job` / `webhook_url` | see [the contract](#the-contract) | | |

Output is MP4. `restore_face` appears in `openapi.yaml` but the REST route ignores it; run [restore](#post-v1videorestore) on the result, or use the MCP `lipsync` tool, which honours it.

```bash
curl -s -X POST http://localhost:8000/v1/video/lipsync \
  -H "Content-Type: application/json" \
  -d '{
    "face_path": "uploads/face.mp4",
    "audio_path": "uploads/voice.wav",
    "engine": "latentsync-1.5",
    "output_path": "out/talking.mp4"
  }'
```

Errors: 404 `ENGINE_NOT_REGISTERED` for an unknown engine, 403 `NONCOMMERCIAL_GATE_REFUSED` for Wav2Lip without the opt-in, 400 when LatentSync runs without CUDA.

## Restore

### `POST /v1/video/restore`

Runs GFPGAN v1.4 over every frame and puts the source audio back. Takes the standard input and output fields and returns MP4. The optional `engine` field in the spec only allows `gfpgan`, and the route always uses `gfpgan`.

```bash
curl -s -X POST http://localhost:8000/v1/video/restore \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "out/talking.mp4",
    "output_path": "out/talking-restored.mp4"
  }'
```

## ffmpeg operations

These run ffmpeg on the CPU in both images, never touch the engine pool, and never evict a loaded model. A non-zero ffmpeg exit is 500 `FFMPEG_FAILED` with the command and the last 2 KB of stderr in `details`.

### `POST /v1/video/trim`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `start_sec` | yes | | Start, in seconds. |
| `end_sec` | yes | | End, in seconds. Must be greater than `start_sec` (400 `end_sec must be > start_sec`). |
| `precise` | no | `false` | `false` copies streams: fast, but the start snaps to a keyframe and can lose up to one GOP. `true` re-encodes with libx264 CRF 18 (preset veryfast) and AAC 192k for frame-accurate cuts. |

Output is MP4.

### `POST /v1/video/concat`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `inputs_paths` / `inputs_urls` | one of | | Two or more inputs, joined in order. Fewer than two is 400 `concat needs >= 2 inputs`. |
| `precise` | no | `false` | `false` stream-copies through the concat demuxer, which needs every input to share codec, timebase and sample aspect ratio. `true` re-encodes to libx264 CRF 18 and AAC 192k so mixed inputs join cleanly. |

Takes the standard output fields. Output is MP4.

### `POST /v1/video/transcode`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `output_format` | no | `mp4` | Container and file extension: `mp4`, `webm`, `mov`, `mkv` or `gif`. |
| `video_codec` | no | ffmpeg's choice | Passed as `-c:v`, for example `libx264`, `libx265`, `libvpx-vp9`, `libaom-av1`. |
| `audio_codec` | no | ffmpeg's choice | Passed as `-c:a`, for example `aac`, `libopus`, `copy`. |
| `crf` | no | | Passed as `-crf`. |
| `preset` | no | | Passed as `-preset`. |
| `fps` | no | source rate (12 for GIF) | Output frame rate. |
| `gif_options` | no | | GIF only: `width` (scales with Lanczos, height follows the aspect) and `loop` (default `0`, loop forever). `palette_mode` is accepted and ignored; GIFs always use one palette generated from the clip. |

```bash
curl -s -X POST http://localhost:8000/v1/video/transcode \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/clip.mp4",
    "output_format": "gif",
    "fps": 10,
    "gif_options": {
      "width": 480
    },
    "output_path": "out/clip.gif"
  }'
```

### `POST /v1/video/scale`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `width`, `height` | yes | | Output size in pixels. |
| `keep_aspect` | no | `true` | `true` scales to fit inside the box and pads the rest (letterbox), so the output is exactly `width` x `height`. `false` stretches. |

Audio is copied. Output is MP4.

### `POST /v1/video/mux_audio`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `video_path_or_url` | yes | | Staged path, or a URL starting with `http://` or `https://`. |
| `audio_path_or_url` | yes | | Same, for the audio. |
| `replace_existing_audio` | no | `true` | Has no effect: the output always takes the video from the first input and only the audio track of the second. |

The video stream is copied, the audio is encoded to AAC, and the output stops at the shorter input. Output is MP4. Takes the standard output fields.

### `POST /v1/video/extract_audio`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `audio_format` | no | `wav` | `wav` (PCM 16-bit), `mp3` (libmp3lame), `m4a` (AAC), `ogg` (Vorbis) or `flac`. Anything else is 400 `unsupported audio format`. |

Takes the standard input and output fields, including `async_job`.

### `POST /v1/video/thumbnail_grid`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `rows`, `cols` | yes | | Grid size. |
| `cell_width`, `cell_height` | no | `320`, `180` | Size of each cell. Frames are scaled to it without keeping the aspect ratio. |

Produces one PNG. ffmpeg's `thumbnail` filter picks one representative frame from each run of 100 frames, so the grid covers the first `rows x cols x 100` frames of the video, not its whole length.

### `POST /v1/video/info`

Takes `file_path` or `file_url` and returns ffprobe data for the first video and audio stream:

```json
{
  "duration_sec": 12.48,
  "width": 1920,
  "height": 1080,
  "fps": 29.97,
  "video_codec": "h264",
  "audio_codec": "aac",
  "bitrate": 4821337,
  "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
  "size_bytes": 7521288
}
```

## Webhooks

Set `webhook_url` together with `async_job: true` and the server POSTs the final job state there when the job ends:

```json
{
  "job_id": "3f0c2a5e-...",
  "status": "complete",
  "result": {
    "path": "jobs/9b1e7d40-....mp4",
    "size": 2211840
  },
  "error": null
}
```

Headers:

| Header | Value |
| --- | --- |
| `X-Webhook-Timestamp` | Unix seconds when the delivery was signed. |
| `X-Webhook-Signature` | `t=<timestamp>,v1=<hex>`, where `<hex>` is HMAC-SHA256 with `FLICKIES_WEBHOOK_SECRET` over `<timestamp>.<raw body>`. Empty `v1=` when no secret is set. |

To verify, recompute the HMAC over the timestamp, a dot and the exact body bytes, and compare in constant time:

```python
import hashlib
import hmac


def verify(secret: bytes, timestamp: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(
        secret,
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    received = signature.split("v1=", 1)[-1]
    return hmac.compare_digest(expected, received)
```

A delivery counts as done on any 2xx. Otherwise the server retries after 30 seconds, 1 minute, 5 minutes, 30 minutes, 2 hours and 12 hours (seven attempts, 30-second timeout each), then logs `webhook dead-letter` and gives up. Retries resend the same body, timestamp and signature, so de-duplicate on them. Pending retries are lost on restart.

## Request headers

| Header | Effect |
| --- | --- |
| `Authorization: Bearer <token>` | Required when `FLICKIES_AUTH_TOKEN` is set. |
| `X-Request-Id` | Used as the request id if it is a UUID or a ULID; otherwise the server makes a UUID4. Echoed on every response and present on every log line. |
| `X-Trace-Id` | Same validation; defaults to the request id. Echoed on every response. Both ids are forwarded on `file_url` downloads and `output_url` uploads. |
| `Idempotency-Key` | On a POST, the first response below 500 for this key, method and path is cached in memory and replayed for later requests with the same key. The body is not compared. Two identical requests in flight at once both run. |

## Errors

Errors are JSON:

```json
{
  "code": "BAD_REQUEST",
  "message": "must provide exactly one of: file_path, file_url",
  "details": {}
}
```

`details` appears only when there is something in it.

| Status | Code | When |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | Input or output rules broken, bad path, bad URL or a private address, unsupported format, LatentSync without CUDA, engine weights not available. |
| 401 | `UNAUTHORIZED` | Token missing (`missing Authorization: Bearer header`) or wrong (`invalid bearer token`). |
| 403 | `NONCOMMERCIAL_GATE_REFUSED` | A Wav2Lip engine without `FLICKIES_ENABLE_NONCOMMERCIAL`. |
| 404 | `NOT_FOUND` | File, job or route not found. |
| 404 | `ENGINE_NOT_REGISTERED` | Engine slug not in the registry. |
| 413 | `PAYLOAD_TOO_LARGE` | Upload over `FLICKIES_MAX_UPLOAD_BYTES`. |
| 422 | `VALIDATION_FAILED` | The body is not valid JSON, or not a JSON object. `details.errors` lists the problems. |
| 429 | `RATE_LIMITED` | Over `FLICKIES_RATE_LIMIT_PER_MIN`. Comes with `Retry-After: 60`. |
| 500 | `FFMPEG_FAILED` | ffmpeg or ffprobe exited non-zero. `details` has `cmd` and `stderr`. |
| 500 | `INTERNAL_SERVER_ERROR` | Inference failed (`wav2lip inference failed: ...` and similar). |
| 502 | `UPSTREAM_FETCH_FAILED` | A `file_url` download or `output_url` upload got an HTTP error or a transport error. |

Inside a job, every failure becomes `error.code` `JOB_FAILED`, with the original error as text in `error.message`.
