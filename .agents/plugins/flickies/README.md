# @psyb0t/flickies

An OpenClaw/MCP plugin that connects your agent to a self-hosted
[flickies](https://github.com/psyb0t/docker-flickies) video API over the
[Model Context Protocol](https://modelcontextprotocol.io).

flickies already serves a Streamable-HTTP MCP endpoint at `/v1/mcp`. This
package is a thin stdio↔HTTP bridge (via
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote)) for MCP clients that
speak local stdio servers — it forwards everything to your running flickies
instance and authenticates with your bearer token when the server requires one.

> flickies is **self-hosted**. This plugin does not ship the video engine — it
> connects to a flickies server that **you** run. See the
> [flickies repo](https://github.com/psyb0t/docker-flickies) to stand one up.

## Tools

The 11 flickies MCP tools become available to your agent: lipsync a face to
audio, restore faces (GFPGAN), and run ffmpeg ops — `transcode`, `trim`,
`concat`, `scale`, `mux_audio`, `extract_audio`, `thumbnail_grid` — plus
`info` (ffprobe) and `list_engines`.

## Configuration

| Env var | Required | Description |
|---|---|---|
| `FLICKIES_URL` | yes | Base URL of your running flickies server, e.g. `http://localhost:8000`. The bridge appends `/v1/mcp`. |
| `FLICKIES_AUTH_TOKEN` | no | Bearer token — only if the flickies server was started with `FLICKIES_AUTH_TOKEN` set. |

## Install

Install it into your OpenClaw agent from ClawHub:

```bash
openclaw plugins install clawhub:@psyb0t/flickies
```

Then set `FLICKIES_URL` (and `FLICKIES_AUTH_TOKEN` if your server uses auth) in
the plugin's environment.

## Native remote MCP (no install)

If your MCP client already supports **remote** Streamable-HTTP servers, you
don't need this bridge — point the client straight at
`$FLICKIES_URL/v1/mcp` with an `Authorization: Bearer <token>` header.

## License

MIT. See [LICENSE](LICENSE).
