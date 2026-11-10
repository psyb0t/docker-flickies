# MCP rules

Prefix: MCP.

The MCP server is `build_mcp_server()` in `src/flickies/mcp_server.py`, mounted at `/v1/mcp` by `build_app()` in `src/flickies/server.py`. The OpenClaw bridge in `.agents/plugins/flickies/` and `server.json` point clients at it.

- **MCP1:** Keep FastMCP stateless with JSON responses (`stateless_http=True`, `json_response=True`) and `streamable_http_path = "/"`, so the endpoint is `/v1/mcp`, not `/v1/mcp/mcp`. The session manager runs inside the app lifespan; without it every MCP request fails with "Task group is not initialized".
- **MCP2:** `mcp_server.py` never imports `server.py`. It gets `cfg`, `registry` and `ffmpeg` injected and uses the same helpers as REST (`resolve_safe`, `files_dir`, `fetch_to_temp`, `FFmpeg`), so behaviour cannot drift. Every tool mirrors a REST route and keeps its argument names.
- **MCP3:** Tools write only to `output_path` under the staging area (`_resolve_output()`); there is no `output_url`, `async_job` or webhook over MCP. Tools report failure by raising `ValueError` with a caller-readable message, translating `EngineNotRegistered` and `NonCommercialOptInRequired` at the tool boundary.
- **MCP5:** The tools are listed in the `mcp_server.py` module docstring and in `docs/mcp.md`, and the count (11) is written out in the README box, `docs/mcp.md`, the skill description in `.agents/skills/flickies/SKILL.md` and the `description` in `.agents/plugins/flickies/openclaw.plugin.json`. Adding, removing or renaming a tool updates all of them in the same change.
- **MCP6:** `.agents/plugins/flickies/bin/cli.js` only launches `mcp-remote` (exact version in `package.json`) against `$FLICKIES_URL/v1/mcp`. stdout is the MCP channel, so diagnostics go to stderr, and the token is passed as a header argument and never logged.
