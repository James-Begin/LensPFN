"""Figures for the Lens Feed claim (calibrated match scores), from replay predictions.

  fig_reliability.png  predicted P(like) vs observed like rate (10 bins, pooled) + counts
  fig_gate.png         (a) gate threshold vs realized precision  (b) precision vs coverage
  gate_table.md        precision at matched coverage (each user's top 30%), paired CIs

usage: python scripts/feedbench_figures.py artifacts/fbtest ../docs/research/figures
Exploratory re-analysis of the pre-registered test predictions (no new model runs).
"""

import glob
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
df = pd.concat(
    [
        pd.read_csv(p, dtype={"arxiv_id": str})
        for p in sorted(glob.glob(f"{src}/**/predictions.csv", recursive=True))
    ]
)
NAMES = {
    "embsig:tabpfnfast": ("TabPFN-3.5-Fast (Lens Feed)", "#7b2d8e", "-"),
    "embsig:tabpfn": ("TabPFN-3.5", "#c77dd9", "--"),
    "emb:logistic+C0.03": ("Logistic on embeddings", "#1f77b4", "-"),
    "embsig:logistic+C0.1": ("Logistic, same inputs", "#17becf", "--"),
    "embsig:lgbm": ("LightGBM, same inputs", "#ff7f0e", "-"),
    "roc:logistic": ("Rocchio-feature logistic (original baseline)", "#7f7f7f", ":"),
    "rocchio:g0.5": ("Rocchio (scores)", "#2ca02c", "-"),
}
PROB = [k for k in NAMES if k != "rocchio:g0.5"]
users = df.user_id.nunique()

# ---- reliability diagram
fig, (ax, axh) = plt.subplots(
    2, 1, figsize=(6.2, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
)
edges = np.linspace(0, 1, 11)
for k in PROB:
    g = df[df.learner == k]
    b = np.clip(np.digitize(g.score, edges) - 1, 0, 9)
    x = [g.score[b == i].mean() for i in range(10) if (b == i).sum() >= 30]
    y = [g.label[b == i].mean() for i in range(10) if (b == i).sum() >= 30]
    name, color, ls = NAMES[k]
    ece = sum(
        abs(g.score[b == i].mean() - g.label[b == i].mean()) * (b == i).mean()
        for i in range(10)
        if (b == i).any()
    )
    brier = g.assign(se=(g.score - g.label) ** 2).groupby("user_id").se.mean().mean()
    ax.plot(
        x,
        y,
        ls,
        marker="o",
        ms=4,
        color=color,
        lw=2 if "tabpfn" in k else 1.4,
        label=f"{name}: Brier {brier:.3f}, pooled ECE {ece:.3f}",
    )
    if k in ("embsig:tabpfnfast", "emb:logistic+C0.03"):
        axh.hist(g.score, bins=edges, histtype="step", color=color, lw=1.5, label=name)
ax.plot([0, 1], [0, 1], color="black", lw=0.8, alpha=0.5, label="perfect calibration")
ax.set_ylabel("Observed like rate")
ax.set_title(
    f"When Lens says X% match, how often do you like it?  Held-out users (n={users})", fontsize=9.5
)
ax.legend(fontsize=7.5, loc="upper left")
ax.set_ylim(0, 1)
axh.set_xlabel("Predicted P(like)")
axh.set_ylabel("Papers")
axh.legend(fontsize=7)
fig.text(
    0.01,
    0.005,
    "Brier = mean per-user score (pre-registered; lower is better). Pooled ECE ignores "
    "per-user differences. Bins <30 papers omitted.\nScholar Inbox ratings; negatives are papers "
    "shown by Scholar Inbox's own ranker.",
    fontsize=6.3,
    color="gray",
)
fig.tight_layout(rect=(0, 0.035, 1, 1))
fig.savefig(out / "fig_reliability.png", dpi=180)

# ---- gate: threshold -> realized precision; precision vs coverage
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4))
ts = np.linspace(0.5, 0.95, 19)
for k in PROB:
    g = df[df.learner == k]
    name, color, ls = NAMES[k]
    prec = [g.label[g.score >= t].mean() if (g.score >= t).sum() >= 50 else np.nan for t in ts]
    a1.plot(ts, prec, ls, color=color, lw=2 if "tabpfn" in k else 1.4, label=name)
a1.plot(
    [0.5, 0.95], [0.5, 0.95], color="black", lw=0.8, alpha=0.5, label="exactly as promised (y = x)"
)
a1.set_xlabel("Notify threshold (match ≥)")
a1.set_ylabel("Share of notified papers actually liked")
a1.set_title("Notification gate: above the line = conservative (over-delivers)", fontsize=10)
a1.legend(fontsize=7)
covs = np.linspace(0.05, 1, 20)
for k in NAMES:
    g = df[df.learner == k]
    name, color, ls = NAMES[k]
    # per-user top-q% by score (ranking quality, threshold-free), pooled
    prec = []
    for q in covs:
        hits = []
        for _, u in g.groupby("user_id"):
            n = max(1, int(round(q * len(u))))
            hits.append(u.nlargest(n, "score").label.to_numpy())
        prec.append(np.concatenate(hits).mean())
    a2.plot(covs, prec, ls, color=color, lw=2 if "tabpfn" in k else 1.4, label=name)
a2.set_xlabel("Coverage: share of each user's papers surfaced")
a2.set_ylabel("Precision (liked)")
a2.set_title("Ranking: precision at matched coverage", fontsize=10)
a2.legend(fontsize=7)
fig.tight_layout()
fig.savefig(out / "fig_gate.png", dpi=180)

# ---- matched-coverage table (top 30% per user), paired bootstrap vs TabPFN-Fast
rng = np.random.default_rng(0)


def top_prec(g, q=0.3):
    return g.groupby("user_id").apply(
        lambda u: u.nlargest(max(1, int(round(q * len(u)))), "score").label.mean()
    )


P = {k: top_prec(df[df.learner == k]) for k in NAMES}
lines = [
    "| Model | Precision in each user's top 30% | Δ vs TabPFN-Fast (95% CI) |",
    "|---|---|---|",
]
ref = P["embsig:tabpfnfast"]
for k in NAMES:
    d = (ref - P[k]).dropna().to_numpy()
    boot = rng.choice(d, (5000, len(d))).mean(1)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    delta = "—" if k == "embsig:tabpfnfast" else f"TabPFN {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}]"
    lines.append(f"| {NAMES[k][0]} | {P[k].mean():.3f} | {delta} |")
gate = ["", "| Model | Notified at match ≥ 0.8 | …of which liked |", "|---|---|---|"]
for k in PROB:
    g = df[df.learner == k]
    hit = g.score >= 0.8
    gate.append(f"| {NAMES[k][0]} | {hit.mean():.1%} | {g.label[hit].mean():.1%} |")
(out / "gate_table.md").write_text(
    "Exploratory re-analysis of held-out test predictions (pre-registered run; no new models).\n\n"
    + "\n".join(lines + gate)
    + "\n"
)
print("\n".join(lines + gate))
print(f"wrote {out}/fig_reliability.png, fig_gate.png, gate_table.md")
