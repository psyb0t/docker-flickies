# Docs and release rules

Prefix: DOC.

## Docs move with the code

- **DOC1:** `README.md` stays a short front door: what it is, the quick start, the Documentation table linking full `https://psyb0t.github.io/docker-flickies/...` URLs (the README is mirrored to Docker Hub, so relative links break), license posture, agent integrations, license and Sponsor. Detail lives in `docs/`, one subject per page. A new docs page gets a row in the README Documentation table and in the `docs/index.md` table.
- **DOC2:** A change a user or agent can see updates the owning docs in the same change:
  - routes, fields, errors, jobs, webhooks, headers: `docs/api.md`;
  - settings: `docs/configuration.md` and `.agents/skills/flickies/references/setup.md`;
  - engines, licenses, `engines.json` fields: `docs/engines.md` and the README box;
  - MCP tools: `docs/mcp.md` and the places in MCP5;
  - images, `/data` layout, weights, prefetch: `docs/deployment.md`;
  - generated clients: `docs/clients.md`;
  - logging: `docs/logging.md`; exposure and limits: `docs/security.md`; new failure messages: `docs/troubleshooting.md`;
  - Make targets, layout, CI: `docs/development.md` and AGENTS.md;
  - anything the skill describes: `.agents/skills/flickies/SKILL.md`.

## The docs site

- **DOC4:** `docs/` is a Jekyll site on just-the-docs `v0.12.0` (`docs/_config.yml`) with the bundled mocha theme in `docs/_sass/`, published by GitHub Pages from `main` `/docs`. Pages carry a `nav_order`; keep `docs/` flat.
- **DOC5:** After changing `docs/`, run `make docs` (GitHub's Pages build image, output in `.testing/docs-site`) and check the output's links before calling it done.

## CHANGELOG

- **DOC9:** `CHANGELOG.md` entries go at the top, below the intro: `## [X.Y.Z] - YYYY-MM-DD`, a summary sentence, then bullets, grouped under `### Added`, `### Changed`, `### Fixed` or `### Security` when there is more than one kind.

## Versions, tags and publishing

- **DOC10:** Releases so far bump `.agents/.codex-plugin/plugin.json` `version` to the release version; `pyproject.toml` has stayed at `0.3.1` and is what `make version`, the image tags from `make build` and `/v1/health` report. `server.json` stays at `0.0.0` in git; the MCP Registry workflow writes the tag's version at publish time.
- **DOC11:** Each release is an annotated tag `vX.Y.Z` on a commit already pushed to `main` whose pipeline succeeded, because the tag pipeline promotes that commit's images instead of building. The tag message's first line is exactly `vX.Y.Z`, then a blank line, then that release's CHANGELOG section without its `##` heading.
- **DOC12:** Pushing a `v*` tag runs `.github/workflows/pipeline.yml`: it waits for the `main` run, re-tags both images as `vX.Y.Z` and `vX.Y.Z-cuda`, creates the GitHub release, then publishes the skill and plugin to ClawHub and `server.json` to the MCP Registry.
