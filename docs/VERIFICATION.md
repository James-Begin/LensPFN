# Packaging verification

Checked locally on 2026-10-05. These are local results. GitHub Actions repeats the automated
checks on each push; its current status is linked from the main README.

| Check | Result |
| --- | --- |
| Python unit tests | 40 pass in the existing environment and in a fresh Python 3.12 environment with only locked core dependencies. |
| JavaScript tests | 30 pass, including invocation from the repo root used by CI. |
| Extension syntax | Every production `.js` file passes `node --check`. |
| Python dependency lock | `uv lock --check` passes; full application sync dry-run requires no lock changes. |
| Seeded demo | 29 positive + 15 negative curated ratings; 300 distinct unrated cs.LG/stat.ML candidates; companion loads it as ready. Removing a citation’s own label still leaves enough context. |
| Profile preservation | The helper refuses an existing root. Demo checks use temporary directories and leave the normal profile untouched. |
| Extension packaging | 20 current source/assets files; manifest targets present; second rebuild produces identical ZIP bytes. |
| Documentation | Relative file links and Markdown heading links pass `scripts/check_submission.py`. |
| Public-file hygiene | No local profile/cache/environment paths or recognized provider/GitHub/private-key credential patterns found in the public source; This is a targeted check, not a complete security audit. |
| Approved video | Exact cut-07 SHA-256 matches. Existing export verification and full decoded-frame stillness reports accompany the file. |
| Submission cleanup | Obsolete TREC-COVID code/CLI/dependency, planning notes, duplicate ZIP, and unused poster removed. Research consolidated under `docs/research/`; current app and benchmark imports verified. |
| Patch whitespace | `git diff --check` passes. |

No new full benchmark was run during documentation/packaging. Reported measurements are
linked to the existing frozen evaluation and exploratory analyses. Existing UI validation
is documented in the [0.7.0 release notes](research/releases/0.7.0.md); this packaging
pass does not claim new live arXiv coverage.

[Reproduce the development checks](../CONTRIBUTING.md) ·
[Demo setup](DEMO.md) · [Video validation](../demo/showcase/README.md#validation).
