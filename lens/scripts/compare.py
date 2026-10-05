"""Rank learner specs across result dirs; pair TabPFN variants against the best baseline.

usage: python scripts/compare.py <result-dir> [<result-dir> ...] [--budget 30]
Best baseline is chosen by mean found@budget among non-TabPFN specs (selection on the
same topics, so it is optimistic for the baseline — conservative for TabPFN).
"""
import argparse
import collections
import csv
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("dirs", nargs="+", type=Path)
parser.add_argument("--budget", type=int, default=30)
parser.add_argument("--top", type=int, default=12)
args = parser.parse_args()

found = collections.defaultdict(dict)   # (spec, budget) -> {qid: found}
ndcg = collections.defaultdict(dict)
for d in args.dirs:
    for path in sorted(d.rglob("rounds.csv")):
        for r in csv.DictReader(path.open()):
            key = (r["learner"], int(r["budget"]))
            found[key][r["query_id"]] = float(r["found"])
            ndcg[key][r["query_id"]] = float(r["residual_ndcg_10"]) if r["residual_ndcg_10"] not in ("", "nan") else np.nan

specs = sorted({s for s, _ in found})
complete = [s for s in specs if (s, args.budget) in found]
mean = {s: np.mean(list(found[(s, args.budget)].values())) for s in complete}
budgets = [b for b in (5, 10, 15, 20, 25, 30, 40, 50) if b <= args.budget]
print(f"{'spec':34s} " + " ".join(f"@{b:<5d}" for b in budgets) + "  rNDCG@10")
for s in sorted(complete, key=lambda s: -mean[s])[: args.top] + [s for s in complete if s.startswith("static")]:
    vals = " ".join(f"{np.mean(list(found[(s, b)].values())):6.2f}" for b in budgets)
    print(f"{s:34s} {vals}  {np.nanmean(list(ndcg[(s, args.budget)].values())):.3f}")

baselines = [s for s in complete if not s.startswith("tabpfn")]
if baselines:
    best = max(baselines, key=lambda s: mean[s])
    print(f"\nBest baseline at @{args.budget}: {best} ({mean[best]:.2f})")
    rng = np.random.default_rng(0)
    for s in sorted([s for s in complete if s.startswith("tabpfn")], key=lambda s: -mean[s]):
        for b in (10, 20, args.budget):
            if (s, b) not in found or (best, b) not in found:
                continue
            q = sorted(set(found[(s, b)]) & set(found[(best, b)]))
            diff = np.array([found[(s, b)][k] - found[(best, b)][k] for k in q])
            boot = rng.choice(diff, (5000, len(diff))).mean(1)
            lo, hi = np.quantile(boot, [.025, .975])
            print(f"  {s:32s} @{b:<3d} {diff.mean():+5.2f} [{lo:+.2f},{hi:+.2f}] "
                  f"W/T/L {(diff > 0).sum()}/{(diff == 0).sum()}/{(diff < 0).sum()}")
