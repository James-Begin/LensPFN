"""Evaluate the pre-registered hypotheses (docs/research/README.md).

usage: python scripts/feedbench_hypotheses.py artifacts/fbtest
"""

import glob
import sys

import numpy as np
import pandas as pd

root = sys.argv[1]
df = pd.concat(
    [
        pd.read_csv(p, dtype={"arxiv_id": str})
        for p in sorted(glob.glob(f"{root}/**/predictions.csv", recursive=True))
    ]
)


def prob_metrics(g):
    y, p = g.label.to_numpy(), g.score.to_numpy()
    b = np.clip((p * 10).astype(int), 0, 9)
    ece = sum(
        abs(p[b == k].mean() - y[b == k].mean()) * (b == k).mean()
        for k in range(10)
        if (b == k).any()
    )
    return pd.Series({"brier": np.mean((p - y) ** 2), "ece": ece})


def mean_day_auc(g):
    vals = []
    for _, d in g.groupby("day"):
        y, s = d.label.to_numpy(), d.score.to_numpy()
        P, N = s[y == 1], s[y == 0]
        if len(P) and len(N):
            vals.append(
                ((P[:, None] > N[None, :]).sum() + 0.5 * (P[:, None] == N[None, :]).sum())
                / (len(P) * len(N))
            )
    return np.mean(vals) if vals else np.nan


M = {
    l: g.groupby("user_id").apply(prob_metrics)
    for l, g in df.groupby("learner")
    if not l.startswith("rocchio")
}
A = {l: g.groupby("user_id").apply(mean_day_auc) for l, g in df.groupby("learner")}
rng = np.random.default_rng(0)


def ci(d):
    d = d[np.isfinite(d)]
    b = rng.choice(d, (5000, len(d))).mean(1)
    return d.mean(), *np.quantile(b, [0.025, 0.975]), len(d)


BASELINES = ["roc:logistic", "emb:logistic+C0.03", "embsig:logistic+C0.1", "embsig:lgbm"]
for t in ["embsig:tabpfnfast", "embsig:tabpfn"]:
    print(f"== {t}")
    for h, metric in (("H1", "brier"), ("H2", "ece")):
        verdicts = []
        for base in BASELINES:
            m, lo, hi, n = ci((M[t][metric] - M[base][metric]).to_numpy())
            verdicts.append(hi < 0)
            print(
                f"  {h} {metric:5s} vs {base:22s} {m:+.4f} [{lo:+.4f}, {hi:+.4f}] n={n}  "
                f"{'below 0' if hi < 0 else 'CI includes/above 0'}"
            )
        print(f"  {h} overall: {'SUPPORTED' if all(verdicts) else 'NOT supported'}")
    m, lo, hi, n = ci((A[t] - A["rocchio:g0.5"]).to_numpy())
    print(
        f"  H3 auc   vs rocchio:g0.5            {m:+.4f} [{lo:+.4f}, {hi:+.4f}] n={n}  "
        f"non-inferiority (lower > -0.02): {'SUPPORTED' if lo > -0.02 else 'NOT supported'}"
    )
