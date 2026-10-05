# Lens Feed — research and evaluation

For the current extension, demo video, and installation, start at the [repository README](../README.md).
For a ready profile, use the [demo setup](../docs/DEMO.md). This document preserves
the research evidence and optional Streamlit workflow.

**In the week we measured (2026-09-25 → 10-02), arXiv announced 11,481 new computer-science
papers. You can read ten.**
Lens Feed ranks each day's new arXiv papers for *you*, learns from every 👍/👎 with
**TabPFN-3.5** (in-context, no training), and highlights papers whose match estimates exceed your selected threshold.

Built for the TabPFN-3.5 hackathon. Runs locally; your ratings never leave your machine.

## Result (held-out users, pre-registered)

We replayed **real explicit 👍/👎 ratings** from [Scholar Inbox](https://github.com/avg-dev/scholar_inbox_datasets)
(120 held-out users, disjoint from the 120 users used for every design decision; each day
every model ranks the papers that user actually rated, using only earlier ratings).
The test plan was frozen before running: [`docs/feed-test-preregistration.md`](docs/feed-test-preregistration.md).

| Model (same inputs unless noted) | Brier ↓ | Calibration error (per-user ECE) ↓ | Ranking AUC |
|---|---|---|---|
| **TabPFN-3.5-Fast** (Lens Feed) | **0.191** | **0.158** | 0.714 |
| **TabPFN-3.5** | **0.190** | **0.154** | 0.718 |
| Logistic regression on embeddings (Scholar Inbox's model family) | 0.208 | 0.179 | 0.696 |
| Logistic regression, same inputs as TabPFN | 0.208 | 0.185 | 0.708 |
| LightGBM, same inputs as TabPFN | 0.258 | 0.256 | 0.669 |
| Rocchio (tuned; scores, not probabilities) | — | — | **0.724** |
| *Added after the test (exploratory):* | | | |
| Logistic + cross-validated calibration, same inputs | 0.201 | 0.171 | 0.703 |
| Platt-calibrated Rocchio (ranks exactly like Rocchio) | 0.203 | 0.177 | 0.724 |
| Your own like rate (constant) | 0.246 | — | 0.500 |

- **H1/H2 supported:** TabPFN's like-probabilities beat *every* pre-registered probabilistic
  baseline on Brier score and calibration error (paired over users, all 95% CIs below zero;
  better Brier for 87/120 users vs. the best baseline).
- **The obvious "why not just calibrate?" check (exploratory, run after the test):** TabPFN
  also beats logistic regression with scikit-learn's cross-validated calibration (Brier
  −0.010 [−0.016, −0.004], 80/120 users) and Platt-calibrated Rocchio (−0.012 [−0.021, −0.004],
  71/120 users). An earlier Platt-Rocchio row (AUC 0.605) was wrong: predictions were saved at
  6 decimals, which tied a third of its scores. TabPFN's own saved scores had < 0.2% ties.
- **H3 not supported:** ranking is about level with tuned Rocchio (−0.005 to −0.010 AUC),
  but the confidence interval misses our pre-set ±0.02 non-inferiority margin. We do not
  claim better ranking. Full numbers: [`docs/results/feedbench.md`](docs/results/feedbench.md).

**Why it matters:** a feed that notifies you needs probabilities you can trust. That is
exactly where TabPFN won. When Lens said **match ≥ 80%**, held-out users liked **86.9%** of
those papers (35% of papers qualified). TabPFN also beats the trivial "predict the user's own
like rate" baseline decisively (Brier 0.191 vs 0.246, better for 102/120 users; exploratory).

![Reliability diagram](docs/figures/fig_reliability.png)

### TabPFN knows what it doesn't know

How many ratings does Lens need? With only *k* ratings ([`fig_coldstart.png`](docs/figures/fig_coldstart.png),
exploratory, dev and test users):
- **2–10 ratings:** logistic regression is confidently wrong (Brier 0.43 at k = 2, worse than a
  coin flip), while TabPFN stays at the user's base rate. It doesn't pretend to know yet.
- **From ~30 ratings:** TabPFN's probabilities beat the user's own like rate on both splits.
- **Ranking:** similarity (Rocchio) ranks better until ~50 ratings, where TabPFN ties it.

The product follows this curve: **similarity ranking while Lens learns; from 30 ratings,
TabPFN scores and orders the feed.**

![Cold-start curve](docs/figures/fig_coldstart.png)

More: [`fig_gate.png`](docs/figures/fig_gate.png) (gate precision vs. threshold; ranking at
matched coverage, where TabPFN ties Rocchio) and tables in [`docs/figures/`](docs/figures/).

Caveat: Scholar Inbox's dislikes are papers its own ranker showed, so this measures
re-ranking and probability quality among plausible papers, not discovery from all of arXiv.

## How it works

1. **Harvest** new papers from arXiv via OAI-PMH (CC0 metadata; ≤ 1 request / 3.5 s, cached).
2. **Embed** title + abstract with `intfloat/e5-small-v2` (cached on disk).
3. **Shortlist** by similarity to your likes/dislikes/interests (Rocchio).
4. **TabPFN-3.5 scores the shortlist** from one row per paper: its embedding plus
   relational signals relative to *your* history — similarity to likes and dislikes,
   shared authors, category overlap, paper age. Your ratings are TabPFN's context: each
   click is a refit (a forward pass), not a training run.
5. **Confidence gate:** papers with match ≥ your threshold go to *Worth reading*.
6. **Explanations:** closest paper you liked, shared authors.

Stages: under 30 ratings (and at least 3 likes and 3 dislikes), Lens ranks by similarity and
shows no scores. Below that point TabPFN's probabilities were no better than the user's own
like rate in our cold-start test. From 30 ratings, TabPFN scores the shortlist and orders it,
so the list is always sorted by the match shown on each card. Trade-off, stated plainly: on
held-out users the two rankers are statistically tied once users have plenty of ratings
(top pick liked 0.851 vs 0.848; AUC 0.714 vs 0.724), but between 30 and 50 ratings similarity
ranked slightly better in the cold-start test. We chose one consistent score.

The product **omits the paper-age signal** used in the benchmarked model. Re-running the
benchmark without it left Brier unchanged (test 0.191 vs 0.191; dev 0.185 vs 0.183;
exploratory), and dropping it removes a skew when you seed old papers you like.

Two leakage fixes were essential (and are in the product): history features are computed
**leave-one-day-out** (papers rated in the same session are near-duplicates with the same
label) and paper **age is measured at rating time**. Without them, flexible models
(TabPFN, LightGBM) learned spurious patterns that do not exist at serving time. If all
ratings come from fewer than 3 days (e.g. one onboarding session), the product falls back
to 5 contiguous rating blocks (cross-fitting).

## Run the optional Streamlit feed

Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync streamlit run src/lens/feed/app.py
```

**Bundled-data Streamlit demo:** open *✨ Try the demo* in the sidebar and load the
**Prior Labs researcher** persona: 29 liked TabPFN-family papers (all cited in the TabPFN-3.5
report) and 15 disliked near-misses (LLM, RL, diffusion), over a bundled week of 8,211 arXiv
cs + stat papers (CC0 metadata). No arXiv harvest is needed; first-use model downloads still require network access. This loader replaces the current Streamlit profile, so use a separate `LENS_FEED_HOME` to preserve your history. It starts past the 30-rating
point, so TabPFN match scores and *Worth reading* are on immediately.

Or with your own taste: *Fetch new papers from arXiv* (sidebar) → seed liked papers by
arXiv ID → rate results. TabPFN weights download on first use; **you must accept the
TabPFN license** ([instructions](https://docs.priorlabs.ai/quickstart)) and set your own
`TABPFN_TOKEN` in the environment — never commit it. Apple Silicon (MPS), CUDA and CPU work;
a re-rank took ~1 s on an M-series Mac in our tests.

## Use it on arXiv (Chrome extension)

The local [Lens for arXiv extension](extension/README.md) adds ratings to arXiv abstract pages and a reading shortlist in the browser side panel. Start the local companion with `uv run --no-sync python -m lens.feed.bridge --device mps` (or `--device cpu`), then load `extension/` unpacked in Chrome. The extension and Streamlit app share the same local profile.

## Reproduce the benchmark

```bash
uv sync --locked --extra semantic --extra tabpfn --extra bench
git clone --depth 1 https://github.com/avg-dev/scholar_inbox_datasets .cache/bench/scholar_inbox_datasets
uv run --no-sync lens bench-prepare --ratings .cache/bench/scholar_inbox_datasets/data/rated_papers.csv \
  --output artifacts/feedbench --users 240 --device cuda          # downloads ~3 GB CC0 arXiv metadata
uv run --no-sync lens bench-run --bench artifacts/feedbench --split test --device cuda \
  --learners embsig:tabpfnfast rocchio:g0.5 emb:logistic+C0.03 --output artifacts/fbtest/run
python scripts/feedbench_report.py artifacts/fbtest
python scripts/feedbench_hypotheses.py artifacts/fbtest
```

Use `--user-shard k/n` to parallelize (we used 8 A10G GPUs). Learner specs are
`<view>:<model>` — see `src/lens/feedbench.py`.

## Licenses and data

- **TabPFN-3.5 weights:** TABPFN-3.5 License v1.0 — non-commercial/evaluation. A commercial
  Lens Feed would need Prior Labs' commercial license or API.
- **arXiv metadata:** CC0 ([API terms](https://info.arxiv.org/help/api/tou.html)); Lens links to
  arXiv abstract pages and never hosts PDFs. Not endorsed by arXiv.
- **Scholar Inbox ratings:** CC BY-NC-ND 4.0 — used only for evaluation; not shipped or
  redistributed. Cite the Scholar Inbox paper ([arXiv:2504.08385](https://arxiv.org/abs/2504.08385)).

## Documentation

Full index: [`docs/README.md`](docs/README.md) — pre-registration, results, research notes, decision log.

## Research log (how we got here)

Lens started as interactive evidence screening on TREC-COVID (`lens prepare/evaluate`,
judged-only pools, BEIR archive). Across ~100 configurations on dev topics — feedback
features, presumed negatives, three embedding models (e5, BGE, MedCPT), past-session
context, CORD-19 metadata, stacking — **no learned model (TabPFN, logistic, LightGBM)
beat tuned Rocchio at finding relevant documents**, and we never ran that held-out test.
TabPFN's one consistent edge there was probability quality for estimating remaining
relevant documents, which motivated building Lens Feed around calibrated match scores.
That code remains in `src/lens/{data,features,learners,evaluate,meta,views,docmeta}.py`.
