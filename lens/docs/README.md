# Research documentation index

For the extension and judging, start at the [main README](../../README.md),
[demo setup](../../docs/DEMO.md), or [setup guide](../../docs/GETTING_STARTED.md).

| File | Contents |
|---|---|
| [`../HANDOFF.md`](../HANDOFF.md) | Handoff: status, how to run, evidence map, open items, submission checklist |
| [`../README.md`](../README.md) | Lens Feed: product, held-out results, setup, reproduction, licenses |
| [`feed-test-preregistration.md`](feed-test-preregistration.md) | Frozen test plan and hypotheses (written before the test run) |
| [`results/feedbench.md`](results/feedbench.md) | Lens Feed benchmark: test (run once) and dev results |
| [`results/trec-covid.md`](results/trec-covid.md) | TREC-COVID screening experiments (dev only) |
| [`figures/fig_reliability.png`](figures/fig_reliability.png) | Reliability diagram, held-out users (Brier + pooled ECE) |
| [`figures/fig_gate.png`](figures/fig_gate.png) | Gate precision vs threshold; ranking precision at matched coverage |
| [`figures/fig_coldstart.png`](figures/fig_coldstart.png) | Quality vs number of ratings (dev + test, exploratory) |
| [`figures/gate_table.md`](figures/gate_table.md), [`figures/coldstart_table.md`](figures/coldstart_table.md) | Tables behind the figures, with paired CIs |
| [`research/01-hackathon-and-ideas.md`](research/01-hackathon-and-ideas.md) | Hackathon brief, TabPFN-3.5 facts, initial brainstorm |
| [`research/02-idea-evaluations.md`](research/02-idea-evaluations.md) | Agent Forklift, Grid Garden, retrieval, and benchmark research |
| [`research/03-decision-log.md`](research/03-decision-log.md) | What was tried, found, and changed — in order |

## Artifacts (not in git; regenerable)
- `artifacts/remote/artifacts/` — pulled experiment outputs: `grid1–5` (TREC-COVID),
  `fb1–3` (Feed dev), `fbtest` (Feed test), manifests; `artifacts/remote/logs/` run logs.
- Large feature caches (TREC-COVID views/metadata ~600 MB, Feed benchmark ~80 MB) remain on
  the GPU instance and are rebuilt by the commands in the main README.
- Scholar Inbox–derived files (CC BY-NC-ND) are evaluation-only; do not redistribute.
