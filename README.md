# flickies

[![CI](https://github.com/psyb0t/docker-flickies/actions/workflows/pipeline.yml/badge.svg?branch=main)](https://github.com/psyb0t/docker-flickies/actions/workflows/pipeline.yml)
[![version](https://raw.githubusercontent.com/psyb0t/docker-flickies/badges/version.svg)](https://github.com/psyb0t/docker-flickies/releases)
[![license](https://raw.githubusercontent.com/psyb0t/docker-flickies/badges/license.svg)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/psyb0t/flickies?style=flat-square)](https://hub.docker.com/r/psyb0t/flickies)

**Video toolkit. One port. Zero cloud. Lipsync, face restore, ffmpeg. Fire-and-forget async jobs. Webhooks. Spec-first OpenAPI; Go + Python clients generated from the same spec.**

The video sibling of [audiolla](https://github.com/psyb0t/docker-audiolla) (audio) and [talkies](https://github.com/psyb0t/docker-talkies) (speech). Same wire format, same async-job model, same bind-mount-`/data` story, same Makefile shape, same `:latest` + `:latest-cuda` split, same opt-in non-commercial gate.

POST a JSON body. Get a video back. Drive it from curl, shell scripts, the generated Go/Python clients, or point an LLM agent at the MCP endpoint.

No account. No subscription. `docker run` and you're done.

---

## What's in the box

| | |
|--|--|
| 👄 **Lipsync** | **LatentSync 1.5** (ByteDance, Apache-2.0, default, CUDA image) + **Wav2Lip / Wav2Lip-GAN** (Rudrabha, fast and low-VRAM, behind `FLICKIES_ENABLE_NONCOMMERCIAL=1`) |
| 🧹 **Face restore** | **GFPGAN v1.4** (TencentARC, Apache-2.0). Cleans up the soft 96×96 Wav2Lip mouth crop, or use it standalone |
| ⚙️ **ffmpeg ops** | Trim · concat · transcode (incl. gif + fps + codec change) · scale · mux audio · extract audio · thumbnail grid. Pure ffmpeg, CPU |
| 📋 **Info** | ffprobe metadata at `/v1/video/info`: duration, codec, fps, dimensions, bitrate |
| 🔗 **MCP server** | 11 tools at `/v1/mcp` so function-calling LLMs can drive the pipeline |
| 📜 **Spec-first** | `openapi.yaml` is the single source; server models, Go client and Python client are all generated from it |
| 🐳 **Hot-swap eviction + idle unload** | One GPU pool, one model resident. A different model evicts the current one. Idle longer than `FLICKIES_IDLE_UNLOAD_SECS` (default 600s) and the sweeper unloads it |

## Quick start

```bash
docker run -d --name flickies \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest

curl -s -X PUT --data-binary @clip.mp4 \
  http://localhost:8000/v1/files/uploads/clip.mp4

curl -s -X POST http://localhost:8000/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/clip.mp4"}' | jq
```

Paths are relative to the staging area, `/data/files` in the container.

`psyb0t/flickies:latest-cuda` (with `--gpus all`) runs every engine at usable speed and is the only image with LatentSync 1.5. The CPU image runs every ffmpeg op, GFPGAN on the CPU, and Wav2Lip on the CPU (about 44s for a 3s clip, fine for short ones).

Weights download from Hugging Face on first use into `/data/hf`, in the standard cache layout any other Hugging Face tool on the same mount can reuse. Set `FLICKIES_ENABLED_ENGINES` or `FLICKIES_PREFETCH_ALL=1` to pull them at boot instead.

Auth is off until you set `FLICKIES_AUTH_TOKEN`. Set it before the port leaves your machine.

## Documentation

Full docs: **[psyb0t.github.io/docker-flickies](https://psyb0t.github.io/docker-flickies/)**

| Section | What's there |
| --- | --- |
| [Getting started](https://psyb0t.github.io/docker-flickies/getting-started/) | First upload, trim, lipsync job and download |
| [Deployment](https://psyb0t.github.io/docker-flickies/deployment/) | Images, `/data` layout, model weights, prefetch, offline staging, upgrades |
| [Configuration](https://psyb0t.github.io/docker-flickies/configuration/) | Every environment variable and its default |
| [REST API](https://psyb0t.github.io/docker-flickies/api/) | Every endpoint, async jobs, webhooks, headers, error codes |
| [Engines](https://psyb0t.github.io/docker-flickies/engines/) | LatentSync, Wav2Lip, GFPGAN, licenses, VRAM, hot-swap |
| [MCP and agents](https://psyb0t.github.io/docker-flickies/mcp/) | The 11 MCP tools, Claude Code, Codex and OpenClaw installs |
| [Generated clients](https://psyb0t.github.io/docker-flickies/clients/) | Go and Python clients and their gaps |
| [Logging](https://psyb0t.github.io/docker-flickies/logging/) | JSON log fields, request ids, redaction, DEBUG |
| [Security](https://psyb0t.github.io/docker-flickies/security/) | What it reaches and stores, what to set before exposing it |
| [Troubleshooting](https://psyb0t.github.io/docker-flickies/troubleshooting/) | Error messages, causes and fixes |
| [Development](https://psyb0t.github.io/docker-flickies/development/) | Make targets, tests, code generation, CI and releases |

## License posture

Wav2Lip variants are trained on LRS2 (non-commercial). The server **refuses to load them** unless `FLICKIES_ENABLE_NONCOMMERCIAL=1` is set in the server env. LatentSync 1.5 (Apache-2.0) is the commercial-safe default, no gate. Details in [Engines](https://psyb0t.github.io/docker-flickies/engines/#licenses).

## Agent integrations

The [skill](https://github.com/psyb0t/docker-flickies/tree/main/.agents/skills/flickies) works in any agent that reads `.agents/skills/` (such as [peen](https://github.com/psyb0t/peen)), and installs natively in Claude Code (`claude plugin install flickies@psyb0t`), Codex (`codex plugin add flickies@psyb0t`) and OpenClaw (`openclaw skills install @psyb0t/flickies`). Marketplace setup and the OpenClaw MCP bridge plugin are in [MCP and agents](https://psyb0t.github.io/docker-flickies/mcp/).

## aigate integration

[aigate](https://github.com/psyb0t/aigate) runs flickies at `/flickies/` (CPU, `FLICKIES=1`) and `/flickies-cuda/` (CUDA, `FLICKIES_CUDA=1`).

## License

WTFPL for flickies itself. Bundled models and vendored code follow their upstream licenses ([THIRD_PARTY.md](https://github.com/psyb0t/docker-flickies/blob/main/THIRD_PARTY.md)), so review them before commercial redistribution.

## Sponsor

<a href="https://www.buymeacoffee.com/psyb0t"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me a Coffee" height="60" width="217"></a>
