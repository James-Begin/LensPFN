# Lens Feed — held-out test plan (frozen before any test-split run)

Written after dev iteration 3 (artifacts/fb3), before running anything on the test split.

## Data
Scholar Inbox ratings (CC BY-NC-ND 4.0, evaluation only) joined to CC0 arXiv metadata;
`artifacts/feedbench` (seed 42): 120 **test** users, disjoint from the 120 dev users used
for all design decisions. Prequential replay: first 30% of each user's ratings (by time)
are history; then up to 30 rating days, each scored using only earlier ratings.
History features use leave-one-day-out (`lodo=True`) and rating-date ages.

## Frozen learners
TabPFN (no tuning): `embsig:tabpfnfast`, `embsig:tabpfn`
Baselines (dev-selected, i.e. optimistic for baselines):
`rocchio:g0.5`, `roc:logistic` (Platt-calibrated Rocchio), `emb:logistic+C0.03`,
`embsig:logistic+C0.1`, `embsig:lgbm`

## Hypotheses (user = unit; paired bootstrap, 5000 resamples, 95% CI)
- **H1 (probability quality):** `embsig:tabpfnfast` has lower Brier score than every
  probabilistic baseline (`roc:logistic`, `emb:logistic+C0.03`, `embsig:logistic+C0.1`,
  `embsig:lgbm`). Supported if each CI of (TabPFN − baseline) is entirely below 0.
- **H2 (calibration):** same comparison on ECE (10 bins).
- **H3 (ranking parity):** AUC of `embsig:tabpfnfast` is not worse than `rocchio:g0.5`
  by more than 0.02 (lower CI bound > −0.02). This is a non-inferiority claim, not superiority.

Report all metrics (AUC, P@1, nDCG@3, top-25% precision, Brier, ECE, gate precision/coverage
at P ≥ 0.8) for all learners, whichever way they come out. No re-runs on test with changed settings.

## Caveat carried into any claim
Negatives are papers Scholar Inbox's own ranker showed (exposure bias); results describe
re-ranking/probability quality among shown papers, not discovery from all of arXiv.
