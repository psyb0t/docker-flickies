#!/usr/bin/env node
// flickies MCP bridge. A thin stdio<->HTTP proxy: forwards MCP over stdio to a
// running flickies server's Streamable-HTTP endpoint (`$FLICKIES_URL/v1/mcp`),
// authenticating with `$FLICKIES_AUTH_TOKEN` when the server requires it.
//
// stdout IS the MCP protocol channel, so diagnostics go to stderr only — the
// sole output here is a fatal pre-launch console.error (user-facing CLI
// output). The token is passed to the proxy as an argv header, never logged.
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const MCP_PATH = "/v1/mcp";

const base = process.env.FLICKIES_URL;

if (!base) {
  console.error(
    `[flickies-mcp] Missing FLICKIES_URL.

Point this bridge at your running flickies server, e.g.:
  export FLICKIES_URL=http://localhost:8000

flickies is self-hosted — see https://github.com/psyb0t/docker-flickies`,
  );
  process.exit(1);
}

const url = `${base.replace(/\/+$/, "")}${MCP_PATH}`;
const token = process.env.FLICKIES_AUTH_TOKEN;
const proxyEntry = require.resolve("mcp-remote/dist/proxy.js");

const args = [proxyEntry, url, "--transport", "http-only"];
if (token) {
  args.push("--header", `Authorization: Bearer ${token}`);
}
args.push(...process.argv.slice(2));

const result = spawnSync(process.execPath, args, { stdio: "inherit" });
process.exit(result.status ?? 1);
