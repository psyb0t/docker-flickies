# Third-party components

flickies itself is WTFPL (see [LICENSE](LICENSE)). This file lists
third-party source code vendored directly into this repository under
`src/flickies/_vendor/`. It does not list dev-only dependencies, PyPI
packages, or model weights downloaded at runtime — only source that is
distributed as part of this repo (and, by extension, the published Docker
images).

| Component | Kind | SPDX license | Source | Vendored at | Note |
|---|---|---|---|---|---|
| ByteDance LatentSync 1.5 | vendored-source | Apache-2.0 | https://github.com/bytedance/LatentSync | `src/flickies/_vendor/latentsync_pkg/` | Full license text: [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt). LatentSync itself re-vendors OpenAI Whisper (MIT) and AnimateDiff-derived code (Apache-2.0) — see below. |
| OpenAI Whisper | vendored-source (re-vendored by LatentSync) | MIT | https://github.com/openai/whisper | `src/flickies/_vendor/latentsync_pkg/whisper/` | Full license text: [LICENSES/MIT.txt](LICENSES/MIT.txt). Pulled in as part of the LatentSync 1.5 vendor drop, not vendored independently. |
| AnimateDiff-derived code | vendored-source (re-vendored by LatentSync) | Apache-2.0 | https://github.com/guoyww/AnimateDiff | `src/flickies/_vendor/latentsync_pkg/` (motion module / UNet code) | Full license text: [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt). Pulled in as part of the LatentSync 1.5 vendor drop, not vendored independently. |
| Wav2Lip-audio | vendored-source (re-vendored by LatentSync) | Apache-2.0 | https://github.com/Rudrabha/Wav2Lip | `src/flickies/_vendor/latentsync_pkg/` | Wav2Lip audio-preprocessing code, re-vendored inside the LatentSync 1.5 tree; covered by LatentSync's Apache-2.0 grant as shipped. Upstream lineage: Rudrabha/Wav2Lip. |
| Rudrabha/Wav2Lip | vendored-source | **NO OSI license** — "personal/research/non-commercial purposes only" per upstream README | https://github.com/Rudrabha/Wav2Lip | `src/flickies/_vendor/wav2lip/` | Not open source. Upstream restricts use to personal/research/non-commercial purposes; commercial use requires contacting the upstream authors directly. See [src/flickies/_vendor/wav2lip/NOTICE](src/flickies/_vendor/wav2lip/NOTICE) for the verbatim restriction. flickies gates loading this engine behind `FLICKIES_ENABLE_NONCOMMERCIAL=1` at runtime (see README "License posture"), but the source code itself still ships in every clone/image regardless of whether the gate is enabled. |

## License texts

Full verbatim upstream license texts referenced above live in
[`LICENSES/`](LICENSES/):

- [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)
- [`LICENSES/MIT.txt`](LICENSES/MIT.txt) (OpenAI copyright, per Whisper's own LICENSE)

Wav2Lip has no OSI license text to include — its restriction is stated
verbatim in [`src/flickies/_vendor/wav2lip/NOTICE`](src/flickies/_vendor/wav2lip/NOTICE).
