---
title: "Deployment"
description: "Run the flickies CPU or CUDA image: tags, ports, the /data layout, model weight downloads, boot prefetch, offline staging, upgrades and aigate."
nav_order: 3
---

# Deployment

flickies ships as two Docker images on Docker Hub. Both serve REST and MCP on port 8000 and keep all state under `/data`. This page covers choosing an image, what lives in `/data`, how model weights arrive, and upgrading.

## Images

| Image | Built from | What it runs |
| --- | --- | --- |
| `psyb0t/flickies:latest` | [Dockerfile](https://github.com/psyb0t/docker-flickies/blob/main/Dockerfile) (`python:3.12-slim-bookworm`, torch CPU) | ffmpeg ops, Wav2Lip, GFPGAN on the CPU |
| `psyb0t/flickies:latest-cuda` | [Dockerfile.cuda](https://github.com/psyb0t/docker-flickies/blob/main/Dockerfile.cuda) (`nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`, torch cu124) | everything, including LatentSync 1.5 |

Each release is also tagged `vX.Y.Z` and `vX.Y.Z-cuda`. Builds from the default branch are tagged `sha-<commit>` and `sha-<commit>-cuda`. Both images are `linux/amd64` only.

The CUDA image needs an NVIDIA GPU and the NVIDIA Container Toolkit on the host. The tested target is an RTX 3060 with 12 GB, which fits LatentSync 1.5 (about 8 GB) with headroom.

### CPU

```bash
docker run -d --name flickies \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest
```

### CUDA

```bash
docker run -d --name flickies \
  --gpus all \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest-cuda
```

Add `-e FLICKIES_AUTH_TOKEN=...` before you publish the port beyond loopback ([Security](security.md)), and `-e FLICKIES_ENABLE_NONCOMMERCIAL=1` only if you may use the Wav2Lip engines ([Engines](engines.md#licenses)).

## Ports

The image exposes 8000. The entrypoint binds `0.0.0.0` inside the container, so the `-p` flag decides who can reach it: `-p 127.0.0.1:8000:8000` keeps it on the host's loopback, `-p 8000:8000` publishes it on every interface. REST and MCP share the port.

## What lives in /data

`/data` is `FLICKIES_DATA_DIR`. Bind-mount it, or every upload, result and downloaded model goes away with the container.

| Path | Holds |
| --- | --- |
| `/data/files/` | The staging area. Every `file_path`, `output_path`, `inputs_paths` entry and `/v1/files/{path}` path is relative to it. Async job results go to `/data/files/jobs/`. |
| `/data/hf/` | The Hugging Face cache (`HF_HOME` is set to `/data/hf` in both images). Model repositories land in `/data/hf/hub/models--<org>--<name>/`. |
| `/data/models/wav2lip/`, `/data/models/gfpgan/` | Optional manual weight files. A non-empty file here wins over the Hugging Face download. |
| `/data/logs/flickies.log` | The rotating JSON log ([Logging](logging.md)). |
| `/data/torch_cache/` | `TORCH_HOME`, for anything torch downloads on its own. |

The entrypoint also creates `/data/uploads/`. Nothing in the server reads or writes it; uploads go to `/data/files/`.

The container runs as root, so files it creates in the bind mount are owned by root on the host.

Nothing cleans up `/data/files/`. Results, async job outputs and uploads stay until you delete them with `DELETE /v1/files/{path}` or from the host.

## Model weights

Engines download their weights from Hugging Face the first time they load. Each download pulls the whole repository, not one file, so the cache matches upstream and any other Hugging Face aware tool sharing the mount can reuse it.

| Engine | Repository | Notes |
| --- | --- | --- |
| `wav2lip`, `wav2lip-gan` | `Nekochu/Wav2Lip` | Includes training-only checkpoints flickies does not use. |
| S3FD face detector (Wav2Lip) | `ByteDance/LatentSync-1.5` | The detector ships in that repository's `auxiliary/` directory, so the first Wav2Lip load downloads the whole LatentSync repository too. |
| `gfpgan` | `leonelhs/gfpgan` | The repository also holds other GFPGAN versions, RestoreFormer and CodeFormer; flickies uses `GFPGANv1.4.pth`. |
| `latentsync-1.5` | `ByteDance/LatentSync-1.5` | CUDA image only. |

`HF_TOKEN` or `HUGGINGFACE_TOKEN` (the entrypoint copies one to the other) is only needed if you point an engine at a gated or private repository.

### Prefetch at boot

By default nothing downloads until a request needs it, and that request waits. To download at boot, before the server starts listening:

- `FLICKIES_ENABLED_ENGINES=latentsync-1.5,gfpgan` downloads just those slugs.
- `FLICKIES_PREFETCH_ALL=1` downloads every engine in the registry (used only when `FLICKIES_ENABLED_ENGINES` is empty).

Prefetch skips an engine marked `cuda_only` when there is no CUDA device, and skips the Wav2Lip engines unless `FLICKIES_ENABLE_NONCOMMERCIAL` is set. A failed download is logged and boot continues; the engine then downloads on its first request. Prefetch only downloads. Engines still load into memory on first use, and every engine in the registry stays callable whatever `FLICKIES_ENABLED_ENGINES` says.

```bash
docker run -d --name flickies \
  --gpus all \
  -e FLICKIES_ENABLED_ENGINES=latentsync-1.5,gfpgan \
  -v "$HOME/flickies-data:/data" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest-cuda
```

### Offline hosts

`FLICKIES_OFFLINE=1` skips the boot prefetch and makes every engine load from local files only. Stage the weights first, either by copying a populated `/data/hf` from a machine that has internet, or by dropping the checkpoint files where the engines look before they try Hugging Face:

| File | Path |
| --- | --- |
| `wav2lip.pth` | `/data/models/wav2lip/wav2lip.pth` |
| `wav2lip_gan.pth` | `/data/models/wav2lip/wav2lip_gan.pth` |
| S3FD detector | `/data/models/wav2lip/s3fd-619a316812.pth` |
| `GFPGANv1.4.pth` | `/data/models/gfpgan/GFPGANv1.4.pth` |

LatentSync 1.5 has no manual path. It needs the `ByteDance/LatentSync-1.5` snapshot in `/data/hf`.

## Custom engine registry

The image reads the engine list from `/app/engines.json` ([source](https://github.com/psyb0t/docker-flickies/blob/main/engines.json)). Mount your own over it, or point `FLICKIES_ENGINES_FILE` at another path, to drop engines or add variants:

```bash
docker run -d --name flickies \
  --gpus all \
  -v "$HOME/flickies-data:/data" \
  -v "$PWD/my-engines.json:/app/engines.json:ro" \
  -p 127.0.0.1:8000:8000 \
  psyb0t/flickies:latest-cuda
```

The fields are described in [Engines](engines.md#the-engine-registry). A missing registry file stops the server at startup.

## Upgrading

```bash
docker pull psyb0t/flickies:latest
docker rm -f flickies
```

Then start it again with the same `docker run`. Everything worth keeping is in `/data`. Async jobs live in memory, so jobs that were running or not yet polled are gone after a restart; their finished files stay in `/data/files/jobs/`.

## Behind aigate

[aigate](https://github.com/psyb0t/aigate) runs flickies as an optional service: `FLICKIES=1` mounts the CPU image at `/flickies/` and `FLICKIES_CUDA=1` mounts the CUDA image at `/flickies-cuda/`, both sharing one data directory.
