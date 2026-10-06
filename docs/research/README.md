# Evaluation and methodology

[Product and video](../../README.md) · [Full reported results](results/feedbench.md) · [Frozen test plan](https://github.com/James-Begin/LensPFN/blob/a4e3f6fb3073f93be3a30736630888451fb3cbc2/docs/research/feed-test-preregistration.md)

Lens uses TabPFN for personal-interest probabilities. The pre-registered experiment
supports better probability quality against the tested probabilistic baselines;
it does **not** establish superior ranking. It uses 120 held-out Scholar Inbox users,
separate from 120 development users. No new benchmark was run during submission cleanup.

## Methodology

The benchmark replays explicit ratings in time order. The first 30% of a user's ratings
form history; each subsequent day is scored using only earlier ratings. All learners
receive identical history. E5 title/abstract embeddings are combined with preference
signals from liked/disliked papers, authors, and categories. History features use
leave-one-day-out cross-fitting; paper age is measured at rating time. The statistical
unit is the user, with paired bootstrap confidence intervals.

The product omits paper age and falls back to five contiguous rating blocks when
history spans fewer than three days. It starts with Rocchio similarity, then uses
TabPFN-3.5 Fast estimates and shortlist ordering after 30 ratings, including at least
three of each label. Citation scoring excludes the cited paper's own rating. The
exploratory no-age variant retained Brier 0.191 on the same test users.

Scholar Inbox's own ranker selected the exposed papers: results measure reranking
among rated papers, rather than discovery over all arXiv.
## Read the evidence

| Document | What it establishes |
| --- | --- |
| [Frozen test plan](https://github.com/James-Begin/LensPFN/blob/a4e3f6fb3073f93be3a30736630888451fb3cbc2/docs/research/feed-test-preregistration.md) | Learners, hypotheses, statistical unit, and exposure-bias caveat fixed before test evaluation. |
| [Full results](results/feedbench.md) | Test/development metrics, paired intervals, hypothesis outcomes, and separately labeled exploratory baselines. |
| [Cold-start table](figures/coldstart_table.md) | Probability quality versus rating count; rationale for the 30-rating threshold. |
| [Matched-coverage table](figures/gate_table.md) | Exploratory precision comparisons and threshold coverage. |

**Brier and ECE are errors: lower is better. AUC measures ranking: higher is better.**
Raw Rocchio similarity is not a probability, so its Brier/ECE are undefined. The
corrected exploratory `rocplatt:g0.5` baseline has Brier **0.203**, per-user ECE
**0.177**, and AUC **0.724**. It differs from the frozen `roc:logistic` baseline
(Brier 0.217, per-user ECE 0.179).

## Diagnostic evidence

The cold-start and matched-coverage tables retain the aggregate evidence used to choose
product thresholds. Superseded plot exports have been removed; the reporting scripts
can generate fresh diagnostics from a new replay. Reliability plots use pooled bins,
whereas the primary table averages calibration error per user. `roc:logistic` is the
original Rocchio-feature logistic baseline, distinct from exploratory `rocplatt:g0.5`.

## Reproduce the benchmark

Run from `LensPFN/lens/`. Full replay needs model access, network downloads, and
substantial compute; unit tests require neither. The metadata download is about 3 GB. On macOS, the LightGBM baseline also
needs OpenMP: `brew install libomp` ([upstream installation guide](https://github.com/lightgbm-org/LightGBM/blob/main/python-package/README.rst)).
This dependency is for benchmark baselines, not the Lens companion. If PyTorch and
LightGBM load conflicting OpenMP runtimes on macOS, run their learner specifications
in separate processes with separate output subdirectories; the reporting scripts
combine those subdirectories. See the [LightGBM FAQ](https://lightgbm.readthedocs.io/en/latest/FAQ.html#lightgbm-crashes-randomly-or-operating-system-hangs-during-or-after-running-lightgbm).

```sh
uv sync --locked --extra semantic --extra tabpfn --extra bench
git clone --depth 1 https://github.com/avg-dev/scholar_inbox_datasets .cache/bench/scholar_inbox_datasets
uv run --no-sync lens bench-prepare --ratings .cache/bench/scholar_inbox_datasets/data/rated_papers.csv \
  --output artifacts/feedbench --users 240 --device cuda
uv run --no-sync lens bench-run --bench artifacts/feedbench --split test --device cuda \
  --learners embsig:tabpfnfast embsig:tabpfn rocchio:g0.5 roc:logistic \
  emb:logistic+C0.03 embsig:logistic+C0.1 embsig:lgbm --output artifacts/fbtest/run
uv run --no-sync python scripts/feedbench_report.py artifacts/fbtest
uv run --no-sync python scripts/feedbench_hypotheses.py artifacts/fbtest
uv run --no-sync python scripts/feedbench_figures.py artifacts/fbtest ../docs/research/figures
```

Use `--user-shard k/n` to parallelize; the original replay used eight A10G GPUs.
`lens bench-coldstart --help` describes the separate exploratory rating-count replay.
Learner specifications are in [feedbench.py](../../lens/src/lens/feedbench.py).
Regenerate the README comparison figure without inference:

```sh
uv run --no-sync python scripts/submission_figure.py
```

It reads reported aggregate metrics; it does not reconstruct private predictions or
invent reliability curves. Use a new output directory when replaying, leaving frozen
evidence intact. Scholar Inbox ratings and derived predictions are evaluation-only
and excluded from Git; see [notices](../../NOTICE.md).

For a repeatable new run, use the same ratings checkout, pass `--metadata-revision`
and `--encoder-revision` commit hashes to `bench-prepare`, and retain its manifest.
The manifest records the input CSV SHA-256, selected users, resolved metadata/model
revisions, seed, and dependency versions; replay configs record runtime and device.
The historical aggregate tables are retained, but the original private predictions
and every original upstream revision are not bundled. Replaying changing upstream
data is therefore not a promise to reproduce the published decimals exactly.
