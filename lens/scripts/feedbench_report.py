"""Report for Lens Feed prequential replay (predictions.csv files under given dirs).

Per learner, averaged per user then across users (users are the statistical unit):
  auc      mean per-day AUC over days with both likes and dislikes
  p@1      was the top-ranked paper of the day a like
  ndcg@3   binary-gain nDCG@3 per day
Probabilistic learners only (logistic, lgbm, tabpfn*), pooled per user:
  brier, ece (10 bins), gate precision/coverage at P >= --gate
Paired bootstrap over users for each TabPFN learner vs the best baseline per metric
(best chosen on these same users -> optimistic for the baseline).

usage: python scripts/feedbench_report.py artifacts/fb1 [--gate 0.8]
"""

import argparse
import collections
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("dirs", nargs="+", type=Path)
ap.add_argument("--gate", type=float, default=0.8)
args = ap.parse_args()

frames = [
    pd.read_csv(p, dtype={"arxiv_id": str})
    for d in args.dirs
    for p in sorted(d.rglob("predictions.csv"))
]
df = pd.concat(frames, ignore_index=True).drop_duplicates(["user_id", "day", "arxiv_id", "learner"])


def auc(y, s):
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return np.nan
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return gt / (len(pos) * len(neg))


def ndcg3(y, s):
    order = np.argsort(-s, kind="stable")[:3]
    dcg = sum(y[i] / np.log2(r + 2) for r, i in enumerate(order))
    ideal = sum(1 / np.log2(r + 2) for r in range(min(3, int(y.sum()))))
    return dcg / ideal if ideal else np.nan


per_user = collections.defaultdict(dict)  # learner -> user -> metrics
probabilistic = lambda name: any(
    k in name for k in ("logistic", "logcal", "lgbm", "tabpfn", "prior", "rocplatt")
)
for (learner, user), g in df.groupby(["learner", "user_id"]):
    days = [(d.label.to_numpy(), d.score.to_numpy()) for _, d in g.groupby("day")]
    ya, sa = g.label.to_numpy(), g.score.to_numpy()
    top = sa >= np.quantile(sa, 0.75)  # coverage-matched gate: each learner's top 25%
    m = {
        "auc": np.nanmean([auc(y, s) for y, s in days]) if days else np.nan,
        "p@1": np.mean([y[np.argmax(s)] for y, s in days]),
        "ndcg@3": np.nanmean([ndcg3(y, s) for y, s in days]),
        "prec_top25": ya[top].mean(),
    }
    if probabilistic(learner):
        y, p = g.label.to_numpy(), g.score.to_numpy()
        m["brier"] = np.mean((p - y) ** 2)
        bins = np.clip((p * 10).astype(int), 0, 9)
        m["ece"] = sum(
            abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean()
            for b in range(10)
            if (bins == b).any()
        )
        hit = p >= args.gate
        m["gate_prec"] = y[hit].mean() if hit.any() else np.nan
        m["gate_cov"] = hit.mean()
    per_user[learner][user] = m

users = sorted(set.intersection(*[set(v) for v in per_user.values()]))
metrics = ["auc", "p@1", "ndcg@3", "prec_top25", "brier", "ece", "gate_prec", "gate_cov"]
rows = []
for learner, d in per_user.items():
    row = {"learner": learner, "users": len(users)}
    for k in metrics:
        vals = [d[u].get(k, np.nan) for u in users]
        row[k] = np.nanmean(vals) if not all(np.isnan(vals)) else np.nan
    rows.append(row)
table = pd.DataFrame(rows).sort_values("auc", ascending=False)
pd.set_option("display.width", 160)
base_rate = df.drop_duplicates(["user_id", "day", "arxiv_id"]).label.mean()
print(
    f"{len(users)} users (common to all learners); like rate among rated papers {base_rate:.3f}\n"
)
print(table.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

rng = np.random.default_rng(0)
print("\nPaired over users: TabPFN learner minus best baseline (95% bootstrap CI)")
for k, better in [
    ("auc", 1),
    ("p@1", 1),
    ("ndcg@3", 1),
    ("prec_top25", 1),
    ("brier", -1),
    ("ece", -1),
]:
    base = table[~table.learner.str.contains("tabpfn")].dropna(subset=[k])
    if base.empty:
        continue
    best = base.sort_values(k, ascending=better < 0).iloc[0].learner
    for t in table[table.learner.str.contains("tabpfn")].learner:
        diff = np.array(
            [per_user[t][u].get(k, np.nan) - per_user[best][u].get(k, np.nan) for u in users]
        )
        diff = diff[np.isfinite(diff)]
        if not len(diff):
            continue
        boot = rng.choice(diff, (5000, len(diff))).mean(1)
        lo, hi = np.quantile(boot, [0.025, 0.975])
        wins = (diff * better > 0).sum()
        print(
            f"  {k:9s} {t:22s} vs {best:20s} {diff.mean():+.4f} [{lo:+.4f},{hi:+.4f}] "
            f"better for {wins}/{len(diff)} users"
        )
