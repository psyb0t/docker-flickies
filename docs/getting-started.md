---
title: "Getting started"
description: "Start the flickies container, upload a clip to the staging area, probe it, trim it, run a lipsync job and download the result."
nav_order: 2
---

# Getting started

This page takes you from nothing to a trimmed clip and a lipsynced video. It uses curl and jq on the host and the CPU image, which is enough for every ffmpeg operation.

## 1. Start the container

```bash
docker run -d --name flickies \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest
```

The container serves REST and MCP on port 8000. Everything it keeps (staged files, model weights, logs) lands in `$HOME/flickies-data` on the host. Check that it is up:

```bash
curl -s http://localhost:8000/healthz
```

```json
{
  "status": "ok"
}
```

`GET /v1/health` gives more: version, device, ffmpeg version, the engines in the registry and which one is loaded.

```bash
curl -s http://localhost:8000/v1/health | jq
```

## 2. Upload a clip

Every video endpoint reads its input either from the staging area (`file_path`) or from a URL the server downloads (`file_url`). The staging area is `/data/files` inside the container, so `$HOME/flickies-data/files` on the host. Upload with a raw-body PUT:

```bash
curl -s -X PUT \
  --data-binary @clip.mp4 \
  http://localhost:8000/v1/files/uploads/clip.mp4 | jq
```

```json
{
  "path": "uploads/clip.mp4",
  "size": 1048576,
  "sha256": "..."
}
```

Copying the file into `$HOME/flickies-data/files/uploads/` on the host works too.

## 3. Probe it

```bash
curl -s -X POST http://localhost:8000/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/clip.mp4"}' | jq
```

The answer carries `duration_sec`, `width`, `height`, `fps`, `video_codec`, `audio_codec`, `bitrate`, `container_format` and `size_bytes`.

## 4. Trim it

A video-producing endpoint needs exactly one output: `output_path` (written into the staging area) or `output_url` (the server PUTs the result there).

```bash
curl -s -X POST http://localhost:8000/v1/video/trim \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/clip.mp4",
    "start_sec": 2,
    "end_sec": 7,
    "precise": true,
    "output_path": "out/clip-trimmed.mp4"
  }' | jq
```

```json
{
  "path": "out/clip-trimmed.mp4",
  "size": 734003
}
```

Download it:

```bash
curl -s -o clip-trimmed.mp4 \
  http://localhost:8000/v1/files/out/clip-trimmed.mp4
```

`precise: true` re-encodes for frame-accurate cuts. Without it, trim copies streams and the start snaps to a keyframe. See [REST API](api.md#post-v1videotrim).

## 5. Lipsync a face to audio

Lipsync needs a face (video or still image) and a driving audio track. On the CPU image the only lipsync engines are Wav2Lip and Wav2Lip-GAN, and they are trained on non-commercial data, so the server refuses them unless you opt in. Restart the container with the opt-in:

```bash
docker rm -f flickies
docker run -d --name flickies \
  -e FLICKIES_ENABLE_NONCOMMERCIAL=1 \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest
```

On a GPU host, use `psyb0t/flickies:latest-cuda` with `--gpus all` instead and leave the opt-in out: the default engine, `latentsync-1.5`, is Apache-2.0. Read [Engines](engines.md) before you choose.

Upload the face and the audio, then submit the job with `async_job`, since lipsync can take minutes:

```bash
curl -s -X PUT --data-binary @face.mp4 \
  http://localhost:8000/v1/files/uploads/face.mp4

curl -s -X PUT --data-binary @voice.wav \
  http://localhost:8000/v1/files/uploads/voice.wav

curl -s -X POST http://localhost:8000/v1/video/lipsync \
  -H "Content-Type: application/json" \
  -d '{
    "face_path": "uploads/face.mp4",
    "audio_path": "uploads/voice.wav",
    "engine": "wav2lip",
    "async_job": true
  }' | jq
```

```json
{
  "job_id": "3f0c...",
  "status": "accepted"
}
```

Poll the job until `status` is `complete` or `failed`:

```bash
curl -s http://localhost:8000/v1/jobs/3f0c... | jq
```

```json
{
  "job_id": "3f0c...",
  "status": "complete",
  "result": {
    "path": "jobs/9b1e....mp4",
    "size": 2211840
  },
  "error": null
}
```

Download `result.path` from `/v1/files/`. The file name under `jobs/` is not the job id, so always read it from `result.path`.

The first lipsync request downloads the engine's Hugging Face repository into `/data/hf`, which takes a while. The request that triggers the download waits for it even with `async_job`, because the engine loads before the job is queued. To download at boot instead, see [Deployment](deployment.md#model-weights).

## Next

- Every endpoint and field: [REST API](api.md)
- Every setting: [Configuration](configuration.md)
- Turn on the bearer token before anyone else can reach the port: [Security](security.md)
