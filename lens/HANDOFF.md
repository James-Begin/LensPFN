# Lens — project handoff

Updated 2026-10-05. The current editable source is this checkout’s `lens/` directory.
Start at the [main README](../README.md), [demo setup](../docs/DEMO.md), and
[getting started](../docs/GETTING_STARTED.md). The original 0.7.0 ZIP is preserved under
[archive/](../archive/README.md).

## Current product

Chrome/Chromium extension with arXiv abstract-page ratings, a personalized side-panel
shortlist and Library, HTML citation previews, automatic DOI/title reference resolution,
background citation scoring, top-citation recommendations, and animated guided setup.
A local authenticated Python companion owns persistence and model execution.

The extension uses TabPFN-3.5 Fast. A fresh profile needs 30 ratings including at least
three of each kind; before that or without model access, similarity remains available
without probability claims. Citation context excludes the cited paper’s own label.
Citation estimates refresh after five rating changes; the main shortlist refreshes after
each change. HTML is supported; native PDF citation interactions are not.

## Run and verify

From `lens/`:

```sh
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync python -m lens.feed.bridge --device cpu
uv run --no-sync python -m unittest discover -s tests -v
node --test tests/test_*.cjs
```

Use `mps` on Apple Silicon or `cuda` with an available NVIDIA GPU. Model access and
first-use downloads are required for live probabilities. Pair via the local companion
page at `127.0.0.1:8765`; no shared credential is supplied. The optional Streamlit app
remains in `src/lens/feed/app.py`.

For a seeded demo profile, run `uv run --no-sync python scripts/prepare_demo.py`, then
start the companion with `--root .lens-feed-demo`. It uses public metadata and 44 curated
example ratings, preserves the normal profile, and refuses an existing destination.

## Evidence map

| Claim | Source |
| --- | --- |
| Pre-registered test; H1/H2 supported, H3 not supported | [Frozen plan](docs/feed-test-preregistration.md), [reported results](docs/results/feedbench.md) |
| Probability quality: Fast Brier 0.191 vs embedding-logistic 0.208 | [Held-out table](docs/results/feedbench.md) |
| Exploratory calibrated baselines, no-age variant, and own-like-rate comparisons | [Results, exploratory section](docs/results/feedbench.md) |
| Cold-start threshold rationale | [Cold-start table](docs/figures/coldstart_table.md), [figure](docs/figures/fig_coldstart.png) |
| Design history and earlier TREC-COVID experiments | [Decision log](docs/research/03-decision-log.md), [research README](README.md) |
| Current features and original validation | [Extension README](extension/README.md), [0.7.0 notes](docs/releases/0.7.0.md) |
| Approved showcase and frame checks | [Demo provenance](../demo/showcase/README.md) |

Do not claim superior ranking. The pre-registered non-inferiority hypothesis was not
supported. Scholar Inbox negatives are exposure-biased; the benchmark evaluates reranking
among plausible exposed papers. The product omits the benchmark’s age signal. Raw ratings
and predictions are evaluation-only and excluded from the repo.

## Submission packaging

The main README now includes the approved 92-second MP4, a poster, feature overview,
setup paths, architecture, evidence, limitations, and a project map. The demo guide
provides an isolated live walkthrough. GitHub Actions runs unit tests and checks the
reproducible extension ZIP. [Contributing](../CONTRIBUTING.md) documents those commands.

The film is a stylized demonstration, with illustrative scores and rating history;
actual model probabilities are computed in the running app. It shows PDF-styled HTML,
not a PDF-viewer feature. Attribution and verification accompany the MP4.

## Remaining product work

- Broader live arXiv DOM coverage across publishers and bibliography formats.
- Faster first-use startup, including an optional public-data embedding bundle.
- Packaging the companion for nontechnical users and browser-store distribution.
- Optional support for works with no identifiable arXiv version.

Source, local data, model licenses, and media have separate terms. See
[notices](../NOTICE.md) and [privacy](../docs/PRIVACY.md). Repository preparation is not an
event submission; confirm event-specific requirements separately before submitting.
