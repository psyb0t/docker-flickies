---
title: "Home"
description: "flickies is a self-hosted video API in one Docker container: lipsync, GFPGAN face restore, ffmpeg ops, async jobs and webhooks over REST and MCP."
nav_order: 1
permalink: /
seo:
  type: WebSite
---

# flickies

flickies is a video toolkit in one Docker container: lipsync (LatentSync 1.5, Wav2Lip), face restore (GFPGAN v1.4), and plain ffmpeg operations (trim, concat, transcode, scale, mux audio, extract audio, thumbnail grid, ffprobe metadata). You POST a JSON body and get a video back, over REST on port 8000 or as MCP tools at `/v1/mcp`.

It is the video sibling of [audiolla](https://github.com/psyb0t/docker-audiolla) (audio) and [talkies](https://github.com/psyb0t/docker-talkies) (speech): same JSON contract, same async-job model, same bind-mounted `/data`, same `:latest` and `:latest-cuda` split. No account, no cloud. Models download from Hugging Face on first use and stay on your disk.

## Install

```bash
docker run -d --name flickies \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest
```

Use `psyb0t/flickies:latest-cuda` with `--gpus all` for LatentSync 1.5 and usable lipsync speed. [Getting started](getting-started.md) walks through the first request.

## You want to

| You want to | Read |
| --- | --- |
| Run it and make the first request | [Getting started](getting-started.md) |
| Pick an image, mount data, prefetch or stage weights | [Deployment](deployment.md) |
| Look up an environment variable | [Configuration](configuration.md) |
| Call an endpoint, poll a job, verify a webhook | [REST API](api.md) |
| Choose a lipsync engine, understand licenses and VRAM | [Engines](engines.md) |
| Drive it from an LLM agent | [MCP and agents](mcp.md) |
| Use the Go or Python client | [Generated clients](clients.md) |
| Read the logs, trace a request | [Logging](logging.md) |
| Put it on a network | [Security](security.md) |
| Fix an error | [Troubleshooting](troubleshooting.md) |
| Change the code | [Development](development.md) |

## What runs where

| Feature | CPU image (`:latest`) | CUDA image (`:latest-cuda`) |
| --- | --- | --- |
| ffmpeg ops and `info` | yes | yes |
| Wav2Lip and Wav2Lip-GAN | yes, slow (needs `FLICKIES_ENABLE_NONCOMMERCIAL=1`) | yes (needs `FLICKIES_ENABLE_NONCOMMERCIAL=1`) |
| GFPGAN face restore | yes, runs on the CPU | yes |
| LatentSync 1.5 | no, its libraries are not in the image | yes |

The project is WTFPL. The models and some vendored code have their own licenses: see [Engines](engines.md#licenses) and [THIRD_PARTY.md](https://github.com/psyb0t/docker-flickies/blob/main/THIRD_PARTY.md).
