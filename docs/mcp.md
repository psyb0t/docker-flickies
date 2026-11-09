---
title: "MCP and agents"
description: "The 11 flickies MCP tools at /v1/mcp, how they differ from REST, and installing the flickies skill and plugin in Claude Code, Codex and OpenClaw."
nav_order: 7
---

# MCP and agents

flickies serves a Model Context Protocol endpoint at `/v1/mcp` on the same port as REST, so a function-calling LLM (LibreChat, Cursor, Claude with an MCP connector) can drive the whole pipeline. The transport is streamable HTTP, stateless, with JSON responses. The bearer token, rate limit and request ids apply exactly as on REST.

The endpoint itself answers at `/v1/mcp/`. A request to `/v1/mcp` gets a `307` redirect there. A client that follows redirects (curl with `-L`, for example) works either way; for one that does not, configure the URL with the trailing slash.

The server is built in [src/flickies/mcp_server.py](https://github.com/psyb0t/docker-flickies/blob/main/src/flickies/mcp_server.py).

## Tools

| Tool | Arguments | Same as |
| --- | --- | --- |
| `list_engines` | none | `GET /v1/engines`, plus `loaded_engine`, without `last_used_secs_ago` |
| `info` | `file_path` or `file_url` | `POST /v1/video/info` |
| `lipsync` | `face_path`/`face_url`, `audio_path`/`audio_url`, `engine` (default `latentsync-1.5`), `restore_face` (default `false`), `output_path` | `POST /v1/video/lipsync` |
| `restore` | `file_path`/`file_url`, `output_path` | `POST /v1/video/restore` |
| `transcode` | `file_path`/`file_url`, `output_format`, `video_codec`, `audio_codec`, `crf`, `preset`, `fps`, `gif_options`, `output_path` | `POST /v1/video/transcode` |
| `trim` | `file_path`/`file_url`, `start_sec`, `end_sec`, `precise`, `output_path` | `POST /v1/video/trim` |
| `concat` | `inputs_paths` or `inputs_urls`, `precise`, `output_path` | `POST /v1/video/concat` |
| `scale` | `file_path`/`file_url`, `width`, `height`, `keep_aspect`, `output_path` | `POST /v1/video/scale` |
| `mux_audio` | `video_path_or_url`, `audio_path_or_url`, `replace_existing_audio`, `output_path` | `POST /v1/video/mux_audio` |
| `extract_audio` | `file_path`/`file_url`, `audio_format`, `output_path` | `POST /v1/video/extract_audio` |
| `thumbnail_grid` | `file_path`/`file_url`, `rows` (default 3), `cols` (default 4), `cell_width`, `cell_height`, `output_path` | `POST /v1/video/thumbnail_grid` |

Field meanings and defaults match the [REST API](api.md). Video-producing tools return `{"path": "<output_path>", "size": <bytes>}`.

## How MCP differs from REST

- **`output_path` is required.** The tools write only into the staging area. There is no `output_url`, no `async_job` and no webhook; every call runs to completion before it answers.
- **`lipsync` honours `restore_face`.** With `restore_face: true` the tool runs GFPGAN over the result in place, which unloads the lipsync engine to load GFPGAN. If `gfpgan` is not in the registry the restore step is skipped silently.
- **No file transfer.** There is no upload or download tool. Stage inputs with `PUT /v1/files/{path}`, pass a `file_url`, and fetch results with `GET /v1/files/{path}`.
- **Errors are tool errors**, not HTTP statuses. Messages match the REST ones, for example `must provide exactly one of: file_path, file_url` or the non-commercial gate text.

## Agent integrations

The repository ships a [skill](https://github.com/psyb0t/docker-flickies/tree/main/.agents/skills/flickies) that teaches an agent the REST API. It works in any agent that reads `.agents/skills/` (such as [peen](https://github.com/psyb0t/peen)) and installs natively in the clients below. Each of them talks to a flickies server you already run, at an address the agent can reach.

### Claude Code

```bash
claude plugin marketplace add psyb0t/agents
claude plugin install flickies@psyb0t
```

Claude Code asks for the flickies URL and, if auth is on, the token. The token is stored in your OS keychain.

### Codex

```bash
codex plugin marketplace add psyb0t/agents
codex plugin add flickies@psyb0t
```

Installed from the marketplace, the skill is invoked as `$flickies:flickies`. Codex also picks the skill up with no install in any repository that contains `.agents/skills/`, where it is invoked as plain `$flickies`.

### OpenClaw

The skill is published to ClawHub on every release:

```bash
openclaw skills install @psyb0t/flickies
```

For MCP clients that speak local stdio, the [@psyb0t/flickies](https://github.com/psyb0t/docker-flickies/tree/main/.agents/plugins/flickies) plugin is a small bridge that runs `mcp-remote` against `$FLICKIES_URL/v1/mcp`:

```bash
openclaw plugins install clawhub:@psyb0t/flickies
```

Then set `FLICKIES_URL` (for example `http://localhost:8000`, the bridge appends `/v1/mcp`) and `FLICKIES_AUTH_TOKEN` if the server needs one.

### MCP Registry

flickies is listed in the official MCP Registry as `io.github.psyb0t/flickies` ([server.json](https://github.com/psyb0t/docker-flickies/blob/main/server.json)), pointing at the `psyb0t/flickies` image with the endpoint `http://localhost:8000/v1/mcp`.
