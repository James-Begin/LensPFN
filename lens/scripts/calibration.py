"""How well does each probabilistic learner estimate screening progress?

At every (topic, budget): estimated total = found + sum of P(relevant) over unreviewed
documents; estimated recall = found / estimated total. Compared with true recall
(found / true total in the judged pool). Lower absolute error is better.

usage: python scripts/calibration.py <result-dir> [...] [--budgets 10 20 30]
"""
import argparse
import collections
import csv
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("dirs", nargs="+", type=Path)
parser.add_argument("--budgets", nargs="+", type=int, default=[10, 20, 30])
args = parser.parse_args()

err = collections.defaultdict(lambda: collections.defaultdict(dict))  # spec -> budget -> qid -> |err|
rel = collections.defaultdict(lambda: collections.defaultdict(dict))  # log ratio of remaining
for d in args.dirs:
    for path in sorted(d.rglob("rounds.csv")):
        for r in csv.DictReader(path.open()):
            if r.get("expected_remaining") in (None, "", "nan"):
                continue
            b = int(r["budget"])
            if b not in args.budgets:
                continue
            found, exp, true = float(r["found"]), float(r["expected_remaining"]), float(r["true_remaining"])
            est_recall = found / max(found + exp, 1e-9)
            true_recall = found / max(found + true, 1e-9)
            err[r["learner"]][b][r["query_id"]] = abs(est_recall - true_recall)
            rel[r["learner"]][b][r["query_id"]] = np.log((exp + 1) / (true + 1))

rank = sorted(err, key=lambda s: np.mean(list(err[s][max(args.budgets)].values())))
print(f"{'learner':36s} " + " ".join(f"|recall err|@{b:<3d}" for b in args.budgets)
      + "  log(est/true remaining)@max")
for s in rank:
    cells = " ".join(f"{np.mean(list(err[s][b].values())):16.3f}" for b in args.budgets)
    print(f"{s:36s} {cells}  {np.mean(list(rel[s][max(args.budgets)].values())):+.2f}")

if len(rank) > 1:
    best_other = [s for s in rank if not s.startswith("tabpfn")]
    if best_other:
        o = best_other[0]
        rng = np.random.default_rng(0)
        print(f"\nPaired vs best non-TabPFN ({o}); negative = TabPFN more accurate")
        for s in [s for s in rank if s.startswith("tabpfn")]:
            b = max(args.budgets)
            q = sorted(set(err[s][b]) & set(err[o][b]))
            diff = np.array([err[s][b][k] - err[o][b][k] for k in q])
            boot = rng.choice(diff, (5000, len(diff))).mean(1)
            lo, hi = np.quantile(boot, [.025, .975])
            print(f"  {s:34s} @{b} {diff.mean():+.3f} [{lo:+.3f},{hi:+.3f}] "
                  f"better on {(diff < 0).sum()}/{len(diff)} topics")
