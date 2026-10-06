"""Plot reported aggregate errors for the README; no inference or private data needed."""
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
results = (ROOT / "docs/research/results/feedbench.md").read_text()
models = [
    ("embsig:tabpfnfast", "TabPFN-3.5 Fast", "#8c253b"),
    ("emb:logistic+C0.03", "Logistic · embeddings", "#a0a5b0"),
    ("embsig:logistic+C0.1", "Logistic · same inputs", "#a0a5b0"),
    ("embsig:lgbm", "LightGBM · same inputs", "#a0a5b0"),
    ("rocplatt:g0.5", "Calibrated Rocchio*", "#dfc49a"),
]
metrics = []
for spec, _, _ in models:
    row = re.search(r"^\s*" + re.escape(spec) + r"\s+120\s+(.+)$", results, re.M)
    if row is None:
        raise ValueError(f"Missing reported metrics for {spec}")
    fields = row.group(1).split()
    metrics.append((float(fields[4]), float(fields[5])))

plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "lens-submission", "font.size": 11})
fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), sharey=True)
fig.set_facecolor("#faf8f7")
for i, (ax, title) in enumerate(zip(axes, ["Brier score", "Per-user calibration error (ECE)"])):
    ax.set_facecolor("#faf8f7")
    for j, (_, _, color) in enumerate(models):
        value = metrics[j][i]
        ax.barh(j, value, color=color, height=.58, hatch="///" if j == 4 else None,
                edgecolor="#b5925e" if j == 4 else color, linewidth=0)
        ax.text(value + .006, j, f"{value:.3f}", va="center", fontsize=11,
                color="#8c253b" if j == 0 else "#403b42", fontweight="bold" if j == 0 else "normal")
    ax.set_xlim(0, .31)
    ax.set_xticks([0, .1, .2, .3])
    ax.set_title(title + " ↓", loc="left", fontsize=13, pad=14, fontweight="bold", color="#242329")
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#e8e3e4", linewidth=.7)
    ax.tick_params(length=0, colors="#655f68")
    for spine in ax.spines.values(): spine.set_visible(False)
axes[0].set_yticks(range(len(models)), [name for _, name, _ in models])
axes[0].invert_yaxis()
fig.suptitle("Better probabilities for your next read", x=.03, ha="left", y=.97,
             fontsize=18, fontweight="bold", color="#242329")
fig.text(.03, .865, "120 held-out users · lower is better on both measures", fontsize=11, color="#655f68")
fig.text(.03, .065, "* Calibrated Rocchio was added after the frozen test (exploratory).", fontsize=9, color="#655f68")
fig.text(.03, .025, "Source: reported Scholar Inbox replay results · raw Rocchio scores have no Brier/ECE", fontsize=9, color="#655f68")
fig.subplots_adjust(left=.27, right=.96, top=.74, bottom=.16, wspace=.2)
output = ROOT / "docs/figures/lens-benchmark.svg"
fig.savefig(output, metadata={"Date": None}, facecolor=fig.get_facecolor())
output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
print(f"Generated {output.relative_to(ROOT)} from reported aggregate metrics.")
