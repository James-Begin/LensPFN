"""Cold-start curve report: ranking (AUC) and probability quality (Brier) vs. ratings k.

usage: python scripts/coldstart_report.py artifacts/remote/cold ../docs/research/figures
Writes fig_coldstart.png and coldstart_table.md. Exploratory (not pre-registered).
"""
import glob
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
NAMES = {"embsig:tabpfnfast": ("TabPFN-3.5-Fast", "#7b2d8e"), "rocchio:g0.5": ("Rocchio (similarity)", "#2ca02c"),
         "emb:logistic+C0.03": ("Logistic on embeddings", "#1f77b4"),
         "embsig:logistic+C0.1": ("Logistic, same inputs", "#17becf"),
         "prior:laplace": ("Your own like rate (constant)", "#999999")}
rng = np.random.default_rng(0)


def auc(y, s):
    P, N = s[y == 1], s[y == 0]
    if not len(P) or not len(N):
        return np.nan
    return ((P[:, None] > N[None, :]).sum() + 0.5 * (P[:, None] == N[None, :]).sum()) / (len(P) * len(N))


def ci(x):
    x = np.asarray(x)[np.isfinite(x)]
    b = rng.choice(x, (4000, len(x))).mean(1)
    return x.mean(), *np.quantile(b, [.025, .975]), len(x)


fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharex=True)
md = []
for col, split in enumerate(["dev", "test"]):
    files = glob.glob(f"{src}/{split}/**/predictions.csv", recursive=True)
    if not files:
        continue
    df = pd.concat([pd.read_csv(p, dtype={"arxiv_id": str}) for p in files])
    cells = df.groupby(["learner", "user_id", "k"]).apply(
        lambda g: pd.Series({"auc": auc(g.label.to_numpy(), g.score.to_numpy()),
                             "brier": np.mean((g.score - g.label) ** 2)})).reset_index()
    # keep (user, k) cells present for every learner
    full = cells.groupby(["user_id", "k"]).learner.nunique() == len(NAMES)
    keep = full[full].index
    cells = cells.set_index(["user_id", "k"]).loc[keep].reset_index()
    ks = sorted(cells.k.unique())
    md += [f"\n### {split} users\n", "| k ratings | users | AUC TabPFN | AUC Rocchio | ΔAUC TabPFN−Rocchio (95% CI) "
           "| Brier TabPFN | Brier best logistic | ΔBrier TabPFN−logistic (95% CI) | Brier own-like-rate | ΔBrier TabPFN−own-rate (95% CI) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for name, (label, color) in NAMES.items():
        if name == "prior:laplace":
            b = [ci(cells[(cells.learner == name) & (cells.k == k)].brier) for k in ks]
            axes[1, col].plot(ks, [x[0] for x in b], color=color, ls="--", lw=1.3, label=label)
            continue
        m = [ci(cells[(cells.learner == name) & (cells.k == k)].auc) for k in ks]
        axes[0, col].errorbar(ks, [x[0] for x in m], yerr=[[x[0] - x[1] for x in m], [x[2] - x[0] for x in m]],
                              color=color, marker="o", ms=3, capsize=2, lw=2 if "tabpfn" in name else 1.3, label=label)
        if name != "rocchio:g0.5":
            b = [ci(cells[(cells.learner == name) & (cells.k == k)].brier) for k in ks]
            axes[1, col].errorbar(ks, [x[0] for x in b], yerr=[[x[0] - x[1] for x in b], [x[2] - x[0] for x in b]],
                                  color=color, marker="o", ms=3, capsize=2, lw=2 if "tabpfn" in name else 1.3, label=label)
    piv = cells.pivot_table(index=["user_id", "k"], columns="learner", values=["auc", "brier"])
    for k in ks:
        p = piv.xs(k, level="k")
        da = ci(p["auc"]["embsig:tabpfnfast"] - p["auc"]["rocchio:g0.5"])
        best = min(["emb:logistic+C0.03", "embsig:logistic+C0.1"], key=lambda c: p["brier"][c].mean())
        db = ci(p["brier"]["embsig:tabpfnfast"] - p["brier"][best])
        dp = ci(p["brier"]["embsig:tabpfnfast"] - p["brier"]["prior:laplace"])
        md.append(f"| {k} | {da[3]} | {p['auc']['embsig:tabpfnfast'].mean():.3f} | {p['auc']['rocchio:g0.5'].mean():.3f} "
                  f"| {da[0]:+.3f} [{da[1]:+.3f}, {da[2]:+.3f}] | {p['brier']['embsig:tabpfnfast'].mean():.3f} "
                  f"| {p['brier'][best].mean():.3f} | {db[0]:+.3f} [{db[1]:+.3f}, {db[2]:+.3f}] "
                  f"| {p['brier']['prior:laplace'].mean():.3f} | {dp[0]:+.3f} [{dp[1]:+.3f}, {dp[2]:+.3f}] |")
    n_users = cells.user_id.nunique()
    axes[0, col].set_title(f"{split} users (n≤{n_users}): ranking", fontsize=10)
    axes[1, col].set_title(f"{split} users: probability quality", fontsize=10)
    axes[1, col].set_xlabel("Ratings the user has given (k)")
    axes[0, col].axvline(50, color="gray", ls=":", lw=1)
    axes[1, col].axvline(30, color="gray", ls=":", lw=1)
for ax in axes[0]:
    ax.set_ylabel("AUC on later papers ↑")
for ax in axes[1]:
    ax.set_ylabel("Brier ↓")
for ax in axes.flat:
    ax.set_xscale("log")
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks([2, 4, 6, 10, 15, 20, 30, 50])
    ax.set_xticklabels(["2", "4", "6", "10", "15", "20", "30", "50"])
axes[0, 0].legend(fontsize=7.5)
axes[1, 0].legend(fontsize=7.5)
fig.suptitle("How many ratings does Lens need?  Fixed later papers; history = the k ratings just before",
             fontsize=10.5)
fig.text(0.01, 0.005, "Dotted lines: product rules chosen from this curve — match scores from 30 ratings, TabPFN ranking from 50. "
         "Cells need ≥1 like and ≥1 dislike. 95% bootstrap CIs over users. Exploratory.",
         fontsize=6.5, color="gray")
fig.tight_layout(rect=(0, 0.02, 1, 0.97))
fig.savefig(out / "fig_coldstart.png", dpi=170)
(out / "coldstart_table.md").write_text("Cold-start curve (exploratory). Brier comparison uses the better of the two "
                                        "logistic baselines at each k.\n" + "\n".join(md) + "\n")
print("\n".join(md))
