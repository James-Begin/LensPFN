# Packaging verification

Checked locally on 2026-10-05. These are local results. GitHub Actions repeats the automated
checks on each push; its current status is linked from the main README.

| Check | Result |
| --- | --- |
| Python unit tests | 46 pass in a fresh Python 3.12 environment with only locked core dependencies. |
| JavaScript tests | 37 pass, including invocation from the repo root used by CI. |
| Extension syntax | Every production `.js` file passes `node --check`. |
| Python dependency lock | `uv lock --check` passes; full application sync dry-run requires no lock changes. |
| Seeded demo | 29 positive + 15 negative curated ratings; 300 distinct unrated cs.LG/stat.ML candidates; companion loads it as ready. Removing a citation’s own label still leaves enough context. |
| Profile preservation | The helper refuses an existing root. Demo checks use temporary directories and leave the normal profile untouched. |
| Extension packaging | 21 current source/assets files; manifest targets present; second rebuild produces identical ZIP bytes. |
| Documentation | Relative file links and Markdown heading links pass `scripts/check_submission.py`. |
| Public-file hygiene | No local profile/cache/environment paths or recognized provider/GitHub/private-key credential patterns found in the public source; This is a targeted check, not a complete security audit. |
| Approved video | Exact cut-07 SHA-256 matches. Existing export verification and full decoded-frame stillness reports accompany the file. |
| Submission cleanup | Obsolete TREC-COVID code/CLI/dependency, planning notes, duplicate ZIP, and unused poster removed. Research consolidated under `docs/research/`; current app and benchmark imports verified. |
| Probability features | Prospective history excludes already-rated papers and freezes the first forecast; strict digest threshold, notification acknowledgment/retries, offline alarm restoration, early uncertainty pilot, and unrated bibliography expectation pass targeted tests. |
| Live feature walkthrough | Real local TabPFN Fast on MPS, isolated public-demo profiles: reliability 1/2 then 2/3; Sharpen queue at 6, 7, and 8 ratings without match percentages; cold-profile digest gating; reference expectation 2.1 → 1.1 on save. Production citation modules tested through the handwritten local fixture. |
| Browser flow and layout | In-app browser desktop and 390px captures inspected; rating/loading/settled frames, abstract expansion, keyboard citation preview, empty digest, and view switching checked. Existing bounded stagger and reduced-motion tests pass. No settled list overlap or horizontal overflow observed. |
| Native Chrome alerts | Worker policy verified with mocked Chrome APIs. Chrome was not connected to automation, so new OS banners, notification clicks, and live arXiv integration were not verified in this pass. |
| Personal profile | Companion restarted on port 8765; personal profile checksum unchanged and 34 ratings retained. Digest stays opt-in. |
| Patch whitespace | `git diff --check` passes. |

No new full benchmark was run during documentation/packaging. Reported measurements are
linked to the existing frozen evaluation and exploratory analyses. Earlier UI validation is documented in the [0.7.0 release notes](research/releases/0.7.0.md).
The [0.8.0 probability features](research/releases/0.8.0.md) add the browser and automated
checks above; this pass does not claim new live arXiv coverage or a cold-start benchmark.

[Reproduce the development checks](../CONTRIBUTING.md) ·
[Demo setup](DEMO.md) · [Video validation](../demo/showcase/README.md#validation).
