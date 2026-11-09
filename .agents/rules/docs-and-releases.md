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
- **DOC3:** A changed project convention updates `AGENTS.md` or the matching file in `.agents/rules/` in the same change.

## The docs site

- **DOC4:** `docs/` is a Jekyll site on just-the-docs `v0.12.0` (`docs/_config.yml`) with the bundled mocha theme in `docs/_sass/`, published by GitHub Pages from `main` `/docs`. Every page has front matter with a unique `title`, a `description` of 50 to 170 characters and a `nav_order`; keep `docs/` flat and keep one `#` heading per page. Link pages with relative `.md` paths and repository files outside `docs/` with full `https://github.com/psyb0t/docker-flickies/blob/main/<path>` URLs.
- **DOC5:** After changing `docs/`, run `make docs` (GitHub's Pages build image, output in `.testing/docs-site`) and check the output's links before calling it done.

## Prose style

- **DOC6:** No em dashes or en dashes in new or changed prose: docs, README, skill, plugin manifests, rules, docstrings, comments, commit and tag messages (`92d35dc`, "drop em dashes from the plugin manifest text"). Use a comma, colon, parentheses or a new sentence. Older text still has them; remove them from lines you edit. Quoted program output stays exact.
- **DOC7:** Keep each prose paragraph on one source line in `README.md` and `docs/`; never hard-wrap. Use plain, specific words with real route, field and variable names, tables for settings, routes and errors, and say what the code does, including the parts that make it look worse.
- **DOC8:** Anything written to other people (release notes, issue replies, the pull request close message in `.github/workflows/collaborators-only.yml`) speaks as one person: "I", never "we", "our" or "the team".

## CHANGELOG

- **DOC9:** Every user-visible change gets a `CHANGELOG.md` entry at the top, below the intro: `## [X.Y.Z] - YYYY-MM-DD`, a summary sentence, then bullets, grouped under `### Added`, `### Changed`, `### Fixed` or `### Security` when there is more than one kind. Versions follow the pre-1.0 semver stated in the CHANGELOG intro: a minor bump may break the REST API and says so, a patch bump is docs, build or fixes only.

## Versions, tags and publishing

- **DOC10:** Releases so far bump `.agents/.codex-plugin/plugin.json` `version` to the release version; `pyproject.toml` has stayed at `0.3.1` and is what `make version`, the image tags from `make build` and `/v1/health` report. Bump versions only when the user asks for a release. `server.json` stays at `0.0.0` in git; the MCP Registry workflow writes the tag's version at publish time.
- **DOC11:** Each release is an annotated tag `vX.Y.Z` on a commit already pushed to `main` whose pipeline succeeded, because the tag pipeline promotes that commit's images instead of building. The tag message's first line is exactly `vX.Y.Z`, then a blank line, then that release's CHANGELOG section without its `##` heading.
- **DOC12:** Pushing a `v*` tag runs `.github/workflows/pipeline.yml`: it waits for the `main` run, re-tags both images as `vX.Y.Z` and `vX.Y.Z-cuda`, creates the GitHub release, then publishes the skill and plugin to ClawHub and `server.json` to the MCP Registry.
- **DOC13:** Commit subjects use `type(scope): summary` (`feat(agents):`, `docs(agents):`, `ci:`), with a body that says what changed and why. Never put `Closes #N`, `Fixes #N` or `Resolves #N` in a commit, tag or release note unless the user said to close that issue.
- **DOC14:** Never commit, tag, push or publish unless the user asked for that specific action in the current turn.
