# Security rules

Prefix: SEC.

flickies is single-tenant: one optional shared token and one staging area every caller can read and write (`docs/security.md`). The repository is public.

## Secrets

- **SEC1:** Never commit, print or quote secrets: `.env` files, tokens, keys, credentials. `.gitignore` excludes the usual secret files; keep them excluded. The entrypoint prints only whether auth is on, never the token. Secret scanning uses gitleaks' default rules (`.gitleaks.toml`).

## Authentication

- **SEC2:** Auth stays ASGI middleware (`BearerAuthMiddleware` in `src/flickies/auth.py`), added innermost in `build_app()` so it covers every route and the `/v1/mcp` mount. The token is compared with `hmac.compare_digest`. Only `/healthz` and `OPTIONS` are exempt (`_EXEMPT_PATHS`); a new route or mount sits behind it (`test_auth_blocks_without_token`).

## Input handling

- **SEC3:** Every caller-supplied staging path goes through `resolve_safe()` (`src/flickies/files.py`): no empty path, NUL, absolute path or `..`, and the resolved path must stay under the root (`test_path_traversal_blocked`). Every `file_url` and `output_url` goes through `_validate_url()` (`src/flickies/fetch.py`): `http` or `https` only, and no private, loopback, link-local, multicast or reserved address unless `FLICKIES_ALLOW_PRIVATE_FETCH` is set. `webhook_url` and redirect targets are not checked today; do not add another unchecked outbound path.
- **SEC4:** Log URLs only through `loggable_url()`, which drops the query string so presigned credentials never reach the logs. `RedactingJsonFormatter` in `src/flickies/logging_config.py` masks keys and values matching `SECRET_RE`; keep new secret-shaped fields under names it matches.
- **SEC5:** Uploads are capped by `FLICKIES_MAX_UPLOAD_BYTES` in `save_stream()`, which deletes the partial file on 413. A new ingress path gets a cap in the same change.
- **SEC6:** External programs run with an argument list through `asyncio.create_subprocess_exec` (`_run()` in `src/flickies/ffmpeg.py`) or `subprocess.run([...])` (GFPGAN remux), never through a shell or string interpolation into a command.

## Models, licenses and images

- **SEC7:** Wav2Lip stays behind the non-commercial gate (ENG6), and the entrypoint keeps announcing the gate state at boot.
- **SEC8:** The engines `torch.load` only the fixed checkpoints from their own Hugging Face repositories or `/data/models/`; never load a checkpoint path a caller supplies.
- **SEC9:** Every third-party source tree vendored under `src/flickies/_vendor/` is listed in `THIRD_PARTY.md` with its license and source, with the license text in `LICENSES/` when the license requires it, and a `NOTICE` for restrictions without an OSI license (`src/flickies/_vendor/wav2lip/NOTICE`).
- **SEC10:** The maintainer's reusable workflows are referenced at `@master` on purpose; do not pin them. `.github/workflows/pipeline.yml` starts from `permissions: {}` and each job grants only what its called workflow needs.
