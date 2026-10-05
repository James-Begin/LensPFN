# Shortlist evaluations (research agents, condensed)

## Agent Forklift — conditional GO, highest execution risk
- Space is crowded: Fail-Fast/Restart-Smart (arXiv 2608.03222), AgentStop, SWE-Router
  (2607.00053), EET (2601.05777), Atropos, SWE-Replay; the *Intervention Paradox*
  (2602.03338) shows accurate failure prediction can still harm outcomes.
- Distinctive angle left: action-conditioned uplift (continue / stop-submit / restart /
  escalate) with abstention, learned from small branched datasets.
- Data: nebius/SWE-agent-trajectories (80,036 traces, CC-BY-4.0, passive only);
  SWE-smith trajectories (row-count discrepancy unresolved). Harness: mini-swe-agent (MIT).
- Blocker: passive traces cannot identify intervention effects; branching snapshots untested.

## Grid Garden — conditional GO, gated on decision headroom
- CityLearn 3.0.2 (MIT); 2023 challenge data CC0 (doi:10.18738/T8/SXFWTI); phase_3_1 is
  2,208 hourly steps × 6 buildings; supplied weather forecasts; two-level TOU tariff
  (on-peak 16–18 h); small battery (4 kWh, 3.32 kW); low carbon variance.
- Dependency friction (CityLearn pins sklearn ≤ 1.2.2, numpy < 2) → two environments.
- Prior art: TabPFN battery arbitrage with mixed economic result (Lipiecki & Weron, 2609.00089).
- Required first gate: oracle vs persistence controller cost gap; simple TOU rule may capture most value.

## Search / retrieval — chosen ("Lens")
- Best mechanism: interactive relevance feedback / active search (TabPFN as per-session
  learner + acquisition), not generic learning-to-rank (already published:
  Vos et al., ICTIR'26, https://github.com/davidvos/pfns-for-ranking).
- Data: TREC-COVID judged pools (explicit 0/1/2; −1 = unjudged), BEIR archive
  (73,876,720 bytes, MD5 ce62140c…). NFCorpus has positive-only qrels → closed-world only.
- Corrections adopted: predict_proba is not a posterior (no "Thompson sampling" claim);
  each label update refits (no gradient training, but not free).

## Lens Feed benchmark search
- Primary: **Scholar Inbox ratings** (https://github.com/avg-dev/scholar_inbox_datasets,
  arXiv 2504.08385): 774,092 explicit ±1 ratings, 13,352 users, 303,413 arXiv papers,
  2022-07 → 2025-02; CC BY-NC-ND 4.0 (evaluation only). Text joined from CC0 arXiv
  metadata (librarian-bots/arxiv-metadata-snapshot, 3.0 GB parquet).
  Caveat: negatives are exposure-biased (shown by Scholar Inbox's own ranker).
- Fallback: CiteULike-a/-t (implicit positives only, no timestamps, license unclear).
- Rejected: OpenAlex citation simulation (heavy ETL, weak "cite ≠ like" labels), SciDocs.
