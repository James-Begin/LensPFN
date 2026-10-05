# Lens Feed — handoff

Status as of 2026-10-04. Hackathon deadline: **October 6** (TabPFN-3.5 Hackathon, Prior Labs).
Submission = runnable repo + optional demo video. Source and version 0.7.0 snapshot are now saved in GitHub at the user’s request.

The Chrome extension now supports citation hover previews, automatic reference resolution, cached match prefetching, a top-citations popup, and animated first-run setup. See `extension/README.md` for installation and `docs/releases/0.7.0.md` for validation.

## 1. What this is (30 seconds)

A personal arXiv paper feed. It ranks each week's new papers for one researcher and shows
a **match %** (TabPFN-3.5's estimate that you'll like the paper), learned in-context from
your 👍/👎. Papers above a threshold go to *Worth reading*. Runs locally.

**The claim (held-out, pre-registered):** on 120 real Scholar Inbox users, TabPFN's
like-probabilities beat every probabilistic baseline on Brier score (0.191 vs 0.208 for
logistic regression on embeddings, Scholar Inbox's model family). Ranking is a statistical
tie with tuned similarity (Rocchio). When Lens says ≥ 80%, users liked 86.9% (among papers
Scholar Inbox showed; base like rate 59.7%).

**Positioning:** every paper feed ranks; Lens tells you how likely you are to like each
paper, tested on held-out users, and says "not sure yet" instead of guessing. Don't claim to
beat Scholar Inbox the product; claim to beat its model family on probability quality.

## 2. Run it

```bash
uv sync --extra semantic --extra tabpfn --extra feed
uv run streamlit run src/lens/feed/app.py
# sidebar → "✨ Try the demo (offline)" → Load: Prior Labs researcher
```

- TabPFN weights need license acceptance + auth on first use
  (https://docs.priorlabs.ai/quickstart; headless: `TABPFN_TOKEN` env var). Without it the
  app shows a message and falls back to similarity ranking (verified on a fresh machine).
- First run downloads e5-small-v2 (embeddings) and TabPFN weights, then embeds the demo week.
  **Measured: 502 s on a CPU-only machine with cold caches** (mostly embedding 8,211 papers);
  on an M-series Mac (MPS), embedding 11,481 papers took 66 s; re-rank after a click ~1 s.
- **On a Wealthsimple machine use `uv run --frozen` / `uv sync --frozen`.** Plain `uv run`
  silently re-locks `uv.lock` against the internal package mirror (happened once). Before
  submitting, `grep -o 'registry = "[^"]*' uv.lock | sort -u` must show only
  `https://pypi.org/simple` (currently: 153 entries, all pypi.org).

## 3. How the product works (src/lens/feed/)

| File | Role |
|---|---|
| `sources.py` | arXiv OAI-PMH harvester (CC0 metadata; ≤ 1 request / 3.5 s; cached in `.cache/arxiv`) |
| `embed.py` | e5-small-v2 embedding cache (`.cache/feed`) |
| `rank.py` | Features + `FeedRanker`. Stage 1: Rocchio shortlist (300 in the app). Stage 2 (≥ 30 ratings, ≥ 3 likes and ≥ 3 dislikes): TabPFN-3.5-Fast scores and orders the shortlist. Input = paper embedding + 10 relational signals (`PRODUCT_SIGNALS`; paper age deliberately excluded). History features are leave-one-day-out; < 3 rating days → 5 rating-order blocks (cross-fitting). |
| `store.py` | Local profile/pool JSON (`.lens-feed/` or `$LENS_FEED_HOME`) |
| `app.py` | Streamlit UI: demo loader, fetch, seed by arXiv ID, cards with match %, why-line, 👍/👎/hide |
| `demo/` | Bundled persona (29 TabPFN-family likes verified via arXiv; 15 near-miss dislikes) + week pool (8,211 cs+stat papers, CC0) |

Demo state at load: 44 ratings → TabPFN on; 84 of 5,475 in-category papers ≥ 80%.

## 4. Evidence and where each number comes from

| Claim | Source |
|---|---|
| Pre-registered test (H1 Brier ✓, H2 per-user ECE ✓, H3 ranking non-inferiority ✗) | `docs/feed-test-preregistration.md`, `docs/results/feedbench.md` (top) |
| Exploratory baselines added after the test: calibrated logistic, corrected Platt-Rocchio, own like rate, no-age variant | `docs/results/feedbench.md` (bottom section) |
| Reliability diagram, gate, matched-coverage ranking | `docs/figures/fig_reliability.png`, `fig_gate.png`, `gate_table.md` |
| Cold-start curve (why the 30-rating threshold) | `docs/figures/fig_coldstart.png`, `coldstart_table.md` |
| How we got here (TREC-COVID phase, pivots, bugs found) | `docs/research/03-decision-log.md` |

Key nuances a judge may probe (all disclosed in README/docs):
- **Pooled ECE favours Platt-Rocchio** (0.048 vs 0.058); the pre-registered metric was
  per-user ECE. Lead with Brier.
- TabPFN beats calibrated logistic by a modest margin (test Brier −0.010 [−0.016, −0.004]).
- Ranking: tie overall; similarity slightly better at 30–50 ratings. User chose TabPFN
  ordering for one consistent score.
- Scholar Inbox negatives are exposure-biased (papers its ranker showed).

## 5. Reproduce

Benchmark (needs GPU for speed; ~3 GB CC0 arXiv metadata download): see README
"Reproduce the benchmark". Learner specs are `view:model` (`src/lens/feedbench.py`):
views `emb`, `embsig`, `embsignoage`, `sig`, `feat`, `roc`, `rocchio`, `rocplatt`, `prior`;
models `tabpfn`, `tabpfnfast`, `logistic+C…`, `logcal+C…`, `lgbm`. Cold-start:
`lens bench-coldstart`. Reports: `scripts/feedbench_report.py`, `feedbench_hypotheses.py`,
`feedbench_figures.py`, `coldstart_report.py`.

## 6. Where things live

| Location | Contents |
|---|---|
| `/Users/james.begin/dev/lens` | Source of truth (code, docs, figures, demo data) |
| `/Users/james.begin/dev/lens.zip` | Shareable snapshot (no artifacts, caches, venv) |
| `/Users/james.begin/dev/lens-with-artifacts.zip` | Older backup incl. raw outputs (pre Phase 5) |
| `lens/artifacts/remote/artifacts/` (git-ignored) | Pulled run outputs: `fb1–3` (dev), `fbtest` (pre-registered test), `fbtest_extra`, `logcal`, `rocplatt`, `noage`, `cold`, `grid1–5` (TREC-COVID) |
| Coder instance `main.Credit-Modeling.jamesbegin.coder:~/lens` | Same code + large feature caches (`artifacts/feedbench` ~80 MB, TREC-COVID views ~600 MB), logs. GPUs: use **0–3** only (4–7 are in use by others). |

Scholar Inbox–derived files (anything under `artifacts/`, `feedbench/ratings.csv`,
predictions) are CC BY-NC-ND: evaluation only, never redistribute or commit.

## 7. Open items (prioritized)

1. **Bundle precomputed demo embeddings** (~6 MB float16) so the demo loads in seconds, not
   minutes, on a judge's CPU machine. Highest-value remaining polish.
2. README hook says Lens "only interrupts you" — there are no notifications; reword to
   "highlights" / *Worth reading*.
3. Remove the engine radio (Fast / 3.5 / similarity) — Fast and 3.5 are statistically identical;
   keep one "compare with similarity" toggle. Rename slider "Notify me when" → "Highlight when".
4. Move TREC-COVID code (`src/lens/{data,features,learners,evaluate,meta,views,docmeta}.py`,
   `scripts/{compare,calibration,run_grid}`, `docs/results/trec-covid.md`) to `legacy/`;
   rename package `lens-search` → `lens-feed`; drop `rank-bm25` from core deps; remove dead
   paths in `rank.py` (`presumed_negatives`, `engine == "logistic"`).
5. Add 3–5 pytest cases for leakage guards (leave-one-day-out, rating-date age, single-session
   cross-fitting, stage thresholds).
6. Screenshot/GIF at the top of README; demo video (being done separately).

## 8. Before submitting — checklist

- [ ] `uv.lock` registries are all `https://pypi.org/simple`; fresh-clone `uv sync` on a public network works
- [ ] **Rotate the TabPFN API key** used during development (it appeared in chat/terminal
      history); delete `~/.cache/tabpfn/auth_token` on the Coder instance
- [ ] No `artifacts/`, `.cache/`, `.lens-feed*/`, Scholar Inbox data in the repo (`.gitignore` covers them)
- [ ] TabPFN-3.5 weights are non-commercial — state in README (done)
- [ ] Every README number matches `docs/results/feedbench.md` / `docs/figures/*.md`
