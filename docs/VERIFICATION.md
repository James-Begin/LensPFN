# Submission verification

Final local checks on 2026-10-06. GitHub Actions repeats the automated checks; the
README badge links to current CI status.

| Check | Result |
| --- | --- |
| Repository audit | Every public file reviewed for runtime, tests, setup, licensing, demo or evaluation purpose. Legacy Streamlit UI/dependencies, old release notes, outdated chart exports and the unused full-week metadata pool removed. |
| Python | 51 tests pass; pinned Ruff formatting and unused-code checks pass. Core tests use no model weights, token, network or personal profile. |
| Extension | 37 JavaScript tests pass; all production scripts pass syntax checks. Formatted source retains the no-build Manifest V3 workflow. |
| Fresh checkout | Archived public source installed in a new Python 3.12 environment; 51 tests, CLI diagnostics, demo preparation/refusal, formatting and ZIP checks pass without a token or downloaded weights. |
| Locked setup | Core and full semantic/TabPFN environments resolve from `uv.lock`; Python package and extension both report 0.8.0. |
| Demo | Separate profile: 29 Interested, 15 Not for me, 300 distinct unrated candidates. Metadata pool reduced from 5.1 MB to 184 KB. Existing destinations are refused. |
| Regression fixes | Saving a DOI-resolved paper reuses verified metadata. Digest restores scores after viewing an empty subject. Setup fixture supports current session storage. |
| Package and links | Deterministic ZIP contains every current extension asset exactly once; local links/anchors and recognized credential patterns checked by the submission script. |
| Benchmark reproduction | Dataset/model revisions can be pinned; manifests record input checksum, users, seed and package versions. Sharding validates `0 ≤ k < n`; full and Fast models have separate caches. Synthetic prepare/replay/report/figure smoke passes, including real Fast/full inference and LightGBM in separate processes. Frozen measurements remain unchanged. |
| Video | Published GitHub attachment: 113.12 s, 1080p/60 fps, H.264/AAC. Full decoded-frame audit found longest hold 2.42 s. [Provenance and checksum](DEMO.md#showcase-provenance). |

Final browser smoke used real local 3.5 Fast on MPS: guided setup retained 44 ratings;
feedback advanced to 46, the prospective check reported 1/1, Sharpen returned six
unrated suggestions with no displayed percentages, and five fixture references scored
with one unavailable. DOI-only BERT resolved to its own identity. The normal profile
was not used. Saving a recommended citation reduced expected remaining relevant
references from 1.1 to 0.1 without changing the other papers’ identities.

The [probability feature validation](research/releases/0.8.0.md) documents earlier real
TabPFN-3.5 Fast checks on Apple Silicon, desktop/narrow browser flows, and remaining-reference
updates. Chrome notification policy is tested with mocked APIs; native OS banners and
all live arXiv variants have not been exhaustively verified. No new full Scholar Inbox
evaluation was run during cleanup; the [research guide](research/README.md) explains the
limits of exact historical reproduction.

[Run these checks](../CONTRIBUTING.md) · [Try the demo](DEMO.md)
