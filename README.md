# flickies

[![Docker Pulls](https://img.shields.io/docker/pulls/psyb0t/flickies?style=flat-square)](https://hub.docker.com/r/psyb0t/flickies)
[![Docker Hub](https://img.shields.io/docker/v/psyb0t/flickies?sort=semver&label=Docker%20Hub&style=flat-square)](https://hub.docker.com/r/psyb0t/flickies)
[![License: WTFPL](https://img.shields.io/badge/License-WTFPL-brightgreen.svg?style=flat-square)](http://www.wtfpl.net/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=flat-square)](https://www.python.org/downloads/)

**Video toolkit. One port. Zero cloud. Lipsync, face restore, ffmpeg. Fire-and-forget async jobs. Webhooks. Spec-first OpenAPI; typed Go + Python clients generated from the same spec.**

The video sibling of [audiolla](https://github.com/psyb0t/docker-audiolla) (audio) and [talkies](https://github.com/psyb0t/docker-talkies) (speech). Same wire format, same async-job model, same bind-mount-`/data` story, same Makefile shape, same `:latest` + `:latest-cuda` split, same opt-in non-commercial gate.

POST a JSON body. Get a video back. Drive it from curl, shell scripts, the generated Go/Python clients, or point an LLM agent at the MCP endpoint.

No account. No subscription. `docker run` and you're done.

---

## What's in the box

| | |
|--|--|
| 👄 **Lipsync** | **LatentSync 1.5** (ByteDance, Apache-2.0, default on CUDA) + **Wav2Lip / Wav2Lip-GAN** (Rudrabha, fast/low-VRAM, behind `FLICKIES_ENABLE_NONCOMMERCIAL=1`) |
| 🧹 **Face restore** | **GFPGAN v1.4** (TencentARC, Apache-2.0) — chains after Wav2Lip to fix the soft 96×96 mouth crop, or use standalone |
| ⚙️ **ffmpeg ops** | Trim · concat · transcode (incl. gif + fps + codec change) · scale · mux audio · extract audio · thumbnail grid — pure ffmpeg, CPU |
| 📋 **Info** | ffprobe metadata at `/v1/video/info` — duration, codec, fps, dimensions, bitrate |
| 🔗 **MCP server** | All endpoints exposed as MCP tools so function-calling LLMs can drive the pipeline |
| 📜 **Spec-first** | `openapi.yaml` is the single source of truth — server-side Pydantic, Go client, and Python client all regenerated from one file |
| 🐳 **Hot-swap eviction + idle unload** | One GPU pool. Different model requested → current model evicted. Idle longer than `FLICKIES_IDLE_UNLOAD_SECS` (default 600s) → unloaded by the sweeper. |

## Quick start

```bash
docker run -d --name flickies \
  -v $HOME/flickies-data:/data \
  -p 8000:8000 \
  psyb0t/flickies:latest

curl -s -X POST http://localhost:8000/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/clip.mp4"}' | jq
```

CUDA image at `psyb0t/flickies:latest-cuda` runs every engine at usable speed. CPU image runs all ffmpeg ops (trim/concat/transcode incl. gif/scale/mux/extract/thumbnail-grid/info) + Wav2Lip-CPU (~44s for a 3s clip; OK for short ones). GFPGAN + LatentSync 1.5 are CUDA-only — CPU image refuses to load them.

Weights are fetched lazily on first call per engine into `/data/models/<slug>/` (S3FD ~85 MB, Wav2Lip ~436 MB each, GFPGAN v1.4 ~350 MB, LatentSync model.tar ~5 GB). `FLICKIES_OFFLINE=1` disables auto-download (operators stage weights out of band).

## MCP

Eleven tools at `/v1/mcp` via streamable-HTTP JSON-RPC: `list_engines`, `info`, `lipsync`, `restore`, `transcode`, `trim`, `concat`, `scale`, `mux_audio`, `extract_audio`, `thumbnail_grid`. Point a function-calling LLM at it (LibreChat, Cursor, Claude desktop with the MCP connector) and it drives the pipeline.

## Hardware ceiling

Tested target: **RTX 3060 12 GB**. Fits LatentSync 1.5 (~8 GB) with headroom. Wav2Lip + GFPGAN chain peaks at ~5 GB. One engine resident at a time — different model request triggers hot-swap eviction.

## License posture

Wav2Lip variants are trained on LRS2 (non-commercial). The server **refuses to load them** unless `FLICKIES_ENABLE_NONCOMMERCIAL=1` is set in the server env. LatentSync 1.5 (Apache-2.0) is the commercial-safe default — no gate.

| Engine | License | Gate |
|--------|---------|------|
| LatentSync 1.5 | Apache-2.0 | none |
| Wav2Lip / Wav2Lip-GAN | LRS2 non-commercial | `FLICKIES_ENABLE_NONCOMMERCIAL=1` |
| GFPGAN | Apache-2.0 | none |
| ffmpeg / ffprobe (not an engine; standard CPU helper) | LGPL (ffmpeg) | none |

Same pattern as audiolla's MusicGen / matchering gates.

## Spec-first

Every request/response shape lives in [`openapi.yaml`](openapi.yaml). The Pydantic models in `src/flickies/schema/_generated.py`, the Go client in `pkg/clients/go/client.gen.go`, and the Python client in `pkg/clients/python/flickies-client/` are all generated from that single file.

```bash
make generate              # regenerate all three (server models + Go client + Python client)
make generate-models       # just server-side Pydantic
make generate-client-go    # just the Go client
make generate-client-python # just the Python client
make generate-check        # CI gate — fail if generated files drift from openapi.yaml
```

Never hand-edit generated files. Edit `openapi.yaml`, run `make generate`, commit everything together.

## Generated clients

### Go

```bash
go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest
```

```go
import flickies "github.com/psyb0t/docker-flickies/pkg/clients/go"

c, _ := flickies.NewClient("http://localhost:8000")
resp, err := c.PostVideoLipsync(ctx, flickies.VideoLipsyncRequest{...})
```

### Python

```bash
pip install "git+https://github.com/psyb0t/docker-flickies.git#subdirectory=pkg/clients/python/flickies-client"
```

```python
from flickies_client import Client
from flickies_client.api.lipsync import post_video_lipsync
from flickies_client.models import VideoLipsyncRequest

client = Client(base_url="http://localhost:8000")
result = post_video_lipsync.sync(client=client, body=VideoLipsyncRequest(...))
```

## aigate integration

Mounts in [aigate](https://github.com/psyb0t/aigate) at `/flickies/` and `/flickies-cuda/` behind the same nginx → `make run-bg` lives. `FLICKIES=1` and `FLICKIES_CUDA=1` toggle the variants.

## License

WTFPL for flickies itself. Bundled models follow their upstream licenses — review before commercial redistribution.
