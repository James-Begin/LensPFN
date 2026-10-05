# Decision log

Chronological record of what was tried, what was found, and why the direction changed.
Numbers come from the result files in `docs/results/` (regenerable from `artifacts/`).

## Phase 1 — Lens (interactive screening on TREC-COVID)
1. **Data design.** Judged-only TREC-COVID pools; grades never used for candidates/features.
   Top-100 fused pools were 35–93% relevant (no headroom) → switched to full judged pools
   (~1,270 docs/topic) and a primary target of *highly relevant* (grade 2, ~19% on dev).
2. **First comparison (10 dev topics, budget 30).** Rocchio 22.1 found; TabPFN 21.7;
   logistic 19.9; static 18.5. TabPFN beat logistic on identical features (+1.8, CI
   +0.4…+3.3) but not Rocchio.
3. **Iterations (≈100 configs, GPUs):** feedback-similarity features, presumed negatives
   (hurt), multi-view embeddings (e5, BGE, MedCPT), per-topic PCA, past-session context
   (lifted logistic to Rocchio level), CORD-19 metadata (informative overall —
   pre-2020 papers 4.9% vs 27.9% highly relevant — but no ranking gain), stacking on the
   tuned Rocchio score. **No learned model beat tuned Rocchio** (best TabPFN −0.75 on 20
   dev topics). TabPFN's consistent edge: remaining-relevance estimates (recall error
   0.025 vs 0.042–0.051 logistic/Platt-Rocchio; tie with LightGBM 0.027).
4. **Held-out TREC-COVID test was never run**, deliberately: no configuration passed the
   dev go/no-go, and repeated dev tuning would have made a test win uninterpretable.

## Phase 2 — product framing
Options considered: Lens Review (screening copilot with a stop-when-done meter),
**Lens Feed** (personal paper feed with a confidence gate), Lens MCP (agent tool).
User chose **Lens Feed**.

## Phase 3 — Lens Feed
1. **Live source.** arXiv API rate-limited this network (HTTP 429); RSS empty on weekends;
   **OAI-PMH works** (official, CC0 metadata). One week of cs: 11,481 new papers in 38 s.
2. **Benchmark.** Scholar Inbox, 240 users (120 dev / 120 test, disjoint), prequential
   day-by-day replay, identical history for all learners.
3. **Dev iteration 1:** Rocchio best AUC (0.756); TabPFN on raw embeddings best-calibrated;
   hand-crafted tabular features hurt every learner.
4. **Bug found — age skew:** history rows' paper age measured *today*, not at rating time.
5. **Bug found — same-day leak:** history features could see same-session near-duplicate
   ratings with the same label; flexible models (TabPFN, LightGBM) exploited it, but it
   never exists at serving time. Fix: **leave-one-day-out** features (unit-tested).
6. **Dev iteration 3 (fixed):** TabPFN (embeddings + signals) ties Rocchio on AUC
   (−0.010, CI −0.034…+0.014) and beats all learned baselines on Brier/ECE.
7. **Pre-registration** (`docs/feed-test-preregistration.md`) written, then **one test run**.
8. **Test result:** H1 (Brier) and H2 (ECE) **supported** vs every probabilistic baseline;
   H3 (AUC within 0.02 of Rocchio) **not supported** (−0.005 to −0.010, CI misses margin).
9. **Product aligned with evidence:** TabPFN only after 10 👍 / 5 👎 (benchmarked regime),
   real dislikes only (no presumed negatives), embeddings + signals input; similarity
   ranking during cold start.

## Phase 4 — post-test analysis and product polish (exploratory)
1. **Figures from the frozen test predictions:** reliability diagram, gate, matched-coverage
   ranking. Gate at 0.8: 35.2% notified, 86.9% liked (conservative). At matched coverage
   TabPFN ties Rocchio and logistic-same-inputs; beats LightGBM, logistic-on-embeddings,
   Platt-Rocchio. Caveat found: **pooled** ECE favours Platt-Rocchio (0.048 vs 0.058);
   the pre-registered per-user ECE favoured TabPFN. Brier is the robust headline.
2. **Trivial baseline added** (own like rate, Laplace): TabPFN-Fast Brier 0.191 vs 0.246,
   better for 102/120 test users.
3. **Cold-start curve** (fixed eval set, history = last k ratings, GPUs 0–3): Rocchio ranks
   better until ~50 ratings; TabPFN probabilities ≈ base rate for k ≤ 10 (logistic is
   badly overconfident) and beat the base rate from ~30 ratings on both splits.
   → **Product changed:** match scores from 30 ratings, TabPFN ranking from 50 (previous
   10👍/5👎 switch was a judgment call the data did not support).
4. **Bug found while building the demo:** one-session onboarding put every rating in one
   leave-one-day-out group (empty training features). Fix: cross-fitting with 5 rating-order
   blocks when ratings span < 3 days.
5. **Offline demo persona** (Prior Labs researcher): 29 TabPFN-family likes verified via
   arXiv OAI-PMH; first version had easy dislikes (robotics/CV) and 198 papers ≥ 80%;
   rebuilt with near-miss dislikes (LLM/RL/diffusion) → 67 of 5,475 papers ≥ 80% (84 after the Phase 5 age/date fixes).

## Phase 5 — judge-perspective review and fixes
1. **Install:** `uv.lock` pointed at an internal package mirror. Regenerated against public
   PyPI (153 entries, all pypi.org); `lightgbm` declared. Fresh-machine test (empty home, no
   token, public PyPI only): install 24 s on a fast link.
2. **No token / license:** the app now shows a clear message and falls back to similarity
   ranking instead of crashing (verified on the fresh machine).
3. **Persona dates** fixed (no rating before submission). **Paper age dropped from the
   product**: benchmark without it unchanged (test Brier 0.191 vs 0.191).
4. **Platt-Rocchio baseline was wrong** (AUC 0.605): predictions were saved at 6 decimals,
   tying 33% of its scores; plus a fragile fit. Rewritten (standardized score, cross-fitted
   history, monotone fallback) and predictions now saved at full precision. Corrected version
   ranks exactly like Rocchio; TabPFN beats it on Brier (test −0.012 [−0.021, −0.004]).
   TabPFN's own saved scores had < 0.2% ties, so pre-registered results stand.
5. **New "why not just calibrate?" baseline:** logistic + cross-validated calibration.
   TabPFN still better on Brier (test −0.010 [−0.016, −0.004], 80/120 users).
6. **Ranking:** user chose TabPFN to order the feed. Evidence: tie on held-out users
   (top pick 0.851 vs 0.848, nDCG@3 0.936 vs 0.931, AUC 0.714 vs 0.724); similarity slightly
   better at 30–50 ratings in the cold-start test. Product: from 30 ratings TabPFN scores *and*
   orders the shortlist (one consistent score); the separate 50-rating stage was removed.
7. **Open:** first demo load on a CPU-only machine with cold caches took 502 s (embedding
   8,211 papers dominates); bundling precomputed demo embeddings would remove most of it.

## Infrastructure notes
- Local: Python 3.11 via internal package index (tabpfn 9.0.0 includes v3.5 / v3.5-fast).
- Remote: Coder instance, 8× A10G; experiments later restricted to **GPUs 4–7** (enforced
  in `scripts/run_grid.sh`). Thread caps needed to avoid CPU oversubscription.
- TabPFN token passed per command via environment; the TabPFN library itself cached it at
  `~/.cache/tabpfn/auth_token` on the instance — delete it when rotating the key.
