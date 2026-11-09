# Testing rules

Prefix: TST.

How to run each target: the Dev workflow table in [AGENTS.md](../../AGENTS.md#dev-workflow) and [docs/development.md](../../docs/development.md).

- **TST1:** `make check` (lint plus unit tests in the dev container) is the gate, and the `code` job in `.github/workflows/pipeline.yml` runs `make lint` and `make test` on every push. It passes on the current tree, and the image build depends on it, so keep it green.
- **TST2:** Unit tests run offline in the dev image, which has no ML stack. Build the app with `build_app()` under a patched environment (`FLICKIES_ENGINES_FILE` pointing at the repo's `engines.json`, `FLICKIES_DATA_DIR` at `tmp_path`, auth and the non-commercial flag removed) and drive it with `fastapi.testclient.TestClient` (`app_client` in `tests/test_server.py`, `base_env` in `tests/test_middleware.py`).
- **TST3:** Tests that need ffmpeg generate their own input with the `lavfi` `testsrc` source and skip when ffmpeg is missing (`test_info_roundtrip_with_real_ffmpeg`, `test_trim_with_real_ffmpeg`). Never commit media fixtures; `tests/integration/.fixtures/*` is gitignored.
- **TST4:** Name tests after the behaviour they pin (`test_path_traversal_blocked`, `test_validate_output_xor_rejects_both`, `test_noncommercial_gate_refuses_when_not_opted_in`). New behaviour gets a test in the same change, in the file for its module.
- **TST5:** `tests/conftest.py` registers the `gpu`, `hf_gated`, `noncommercial` and `engine(*slugs)` markers for integration tests. No integration suite exists in `tests/integration/` yet; a change that alters real inference says which engines it ran by hand and which it could not (no GPU).
- **TST6:** `make test-unit-cov-gate` keeps 80% line coverage on `flickies.config`, `flickies.engines.base`, `flickies.engines._license_gate` and `flickies.engines._registry`. A change to those modules keeps the gate green.
