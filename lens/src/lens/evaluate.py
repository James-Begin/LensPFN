"""Budget-accounted oracle feedback, residual metrics, and topic-paired summaries.

Topics advance in lockstep: at each budget step every topic acquires one label,
then all TabPFN refits for that step run as one batched forward pass.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np

from lens.learners import RelevanceLearner, make_tabpfn, parse_spec, tabpfn_batch

FIELDS = ["query_id", "learner", "budget", "found", "pool_recall", "residual_ndcg_10",
          "update_seconds", "feedback_used", "acquired_doc_id", "acquired_grade",
          "expected_remaining", "true_remaining"]


def residual_ndcg(grades, scores, labeled, k=10):
    available = np.ones(len(grades), dtype=bool)
    available[labeled] = False
    remaining = grades[available]
    ranked = remaining[np.argsort(-scores[available], kind="stable")[:k]]
    ideal = np.sort(remaining)[::-1][:k]

    def dcg(values):
        return float(np.sum((2.0 ** values - 1) / np.log2(np.arange(len(values)) + 2)))
    denominator = dcg(ideal)
    return dcg(ranked) / denominator if denominator else float("nan")


def summarize(rows, seed, reference=None):
    learners = sorted({r["learner"] for r in rows})
    budgets = sorted({r["budget"] for r in rows})
    summary = {"curves": [], "paired_differences": []}
    for learner in learners:
        for budget in budgets:
            subset = [r for r in rows if r["learner"] == learner and r["budget"] == budget]
            item = {"learner": learner, "budget": budget, "topics": len(subset)}
            for metric in ["found", "pool_recall", "residual_ndcg_10", "update_seconds"]:
                values = np.array([r[metric] for r in subset], dtype=float)
                finite = values[np.isfinite(values)]
                item[metric] = float(finite.mean()) if len(finite) else None
                item[f"{metric}_topics"] = len(finite)
            summary["curves"].append(item)
    rng = np.random.default_rng(seed)
    tabpfn = [name for name in learners if name.startswith("tabpfn")]
    others = [name for name in learners if not name.startswith("tabpfn")]
    for budget in budgets:
        by_topic: dict[str, dict] = {}
        for row in rows:
            if row["budget"] == budget:
                by_topic.setdefault(row["query_id"], {})[row["learner"]] = row
        for a in tabpfn:
            for b in others:
                for metric in ["found", "residual_ndcg_10"]:
                    diff = np.array([t[a][metric] - t[b][metric] for t in by_topic.values()
                                     if a in t and b in t], dtype=float)
                    diff = diff[np.isfinite(diff)]
                    if not len(diff):
                        continue
                    means = rng.choice(diff, size=(2000, len(diff)), replace=True).mean(axis=1)
                    summary["paired_differences"].append({
                        "budget": budget, "metric": metric, "a": a, "b": b,
                        "topics": len(diff), "mean_difference": float(diff.mean()),
                        "wins": int((diff > 0).sum()), "ties": int((diff == 0).sum()),
                        "losses": int((diff < 0).sum()),
                        "bootstrap_95_percent_interval": np.quantile(means, [.025, .975]).tolist(),
                    })
    summary["warning"] = "Topic bootstrap with one feedback seed; exploratory unless on held-out test."
    return summary


def evaluate(*, features: Path, output: Path, names: list[str], budget: int,
             initial: int, policy: str, seed: int, device: str, version: str, estimators,
             relevant_grade: int = 2, meta_features: Path | None = None, meta_folds: int = 4,
             max_batch: int | None = None):
    if not 0 <= initial <= budget:
        raise ValueError("Require 0 <= --initial <= --budget")
    if len(set(names)) != len(names):
        raise ValueError("Learner names must be unique")
    for name in names:
        parse_spec(name)
    manifest = json.loads((features / "manifest.json").read_text())
    qids = manifest["selected_topics"]
    if not qids:
        raise ValueError("No topic pools available")
    topics = {}
    for qid in qids:
        with np.load(features / f"topic-{qid}.npz", allow_pickle=False) as source:
            topics[qid] = {key: source[key] for key in source.files}
    meta_topics = None
    if meta_features is not None:
        meta_manifest = json.loads((meta_features / "manifest.json").read_text())
        overlap = set(meta_manifest["selected_topics"]) & set(qids)
        if overlap:
            raise ValueError(f"--meta-features shares topics with evaluated set: {sorted(overlap)}")
        meta_topics = {}
        for qid in meta_manifest["selected_topics"]:
            with np.load(meta_features / f"topic-{qid}.npz", allow_pickle=False) as source:
                meta_topics[qid] = {key: source[key] for key in source.files}
    if budget > min(len(t["grades"]) for t in topics.values()):
        raise ValueError("Budget exceeds the smallest pool")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty; use a new result directory")
    output.mkdir(parents=True, exist_ok=True)
    config = {
        "feature_manifest": manifest, "learners": names, "budget": budget,
        "initial": initial, "policy": policy, "seed": seed, "device": device,
        "tabpfn_version": version, "tabpfn_estimators": estimators,
        "relevant_grade": relevant_grade,
        "meta_context": (f"all topics of {meta_features}" if meta_features else
                         f"leave-fold-out over evaluated topics, {meta_folds} folds"),
        "feedback": f"binary label = judgment >= {relevant_grade}; every acquired label counted including initialization",
        "presumed_negatives": "random unlabeled docs labeled 0 in classifier context only; never reviewed, not counted",
        "recall_denominator": "relevant documents in fixed candidate pool, not entire corpus",
        "residual_metric": "graded nDCG@10 excluding all acquired documents; undefined when no positives remain",
        "update_seconds": "TabPFN: batched wall time / topics in batch (amortized), not single-session latency",
        "scope": "judged-pool simulation, not full-corpus recall or real-user evaluation",
        "packages": {},
    }
    for package in ["numpy", "scikit-learn", "tabpfn", "sentence-transformers", "torch"]:
        try:
            config["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    (output / "config.json").write_text(json.dumps(config, indent=2))

    model = None
    if any(parse_spec(n)[0] == "tabpfn" for n in names):
        model = make_tabpfn(seed=seed, device=device, version=version, estimators=estimators)
    rows = []
    with (output / "rounds.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for name in names:
            started = time.perf_counter()
            kind, options = parse_spec(name)
            label = f"{name}@{version}" if kind == "tabpfn" and version != "3.5" else name
            tables = {}
            if options["meta"]:
                from lens.meta import build_table, folds
                if meta_topics is not None:
                    table = build_table(meta_topics, name, relevant_grade=relevant_grade, seed=seed)
                    tables = {qid: table for qid in topics}
                else:
                    assign = folds(qids, meta_folds)
                    for f in range(meta_folds):
                        train = {q: topics[q] for q in qids if assign[q] != f}
                        table = build_table(train, name, relevant_grade=relevant_grade, seed=seed)
                        tables.update({q: table for q in qids if assign[q] == f})
                sizes = sorted({len(t[1]) for t in tables.values()})
                print(f"{label}: past-session context rows {sizes}", flush=True)
            state = {}
            for qid, topic in topics.items():
                topic_seed = (seed + int(hashlib.sha256(qid.encode()).hexdigest()[:8], 16)) % (2**32)
                learner = RelevanceLearner(name, topic, seed=seed, rng_seed=topic_seed + 1)
                learner.meta = tables.get(qid)
                state[qid] = {
                    "learner": learner,
                    "rng": np.random.default_rng(topic_seed),
                    "y": (topic["grades"] >= relevant_grade).astype(int),
                    "order": np.argsort(-topic["base"], kind="stable"),
                    "labeled": [], "scores": topic["base"].astype(float).copy(),
                }
            for spent in range(budget + 1):
                acquired = {}
                for qid, s in state.items():
                    acquired[qid] = None
                    if spent:
                        taken = set(s["labeled"])
                        if spent <= initial or policy == "passive" or name == "static":
                            pick = next(int(i) for i in s["order"] if i not in taken)
                        elif policy == "random":
                            pick = int(s["rng"].choice([i for i in range(len(s["y"])) if i not in taken]))
                        else:
                            masked = np.where(np.isin(np.arange(len(s["y"])), s["labeled"]), -np.inf, s["scores"])
                            pick = int(np.argmax(masked))
                        s["labeled"].append(pick)
                        acquired[qid] = pick
                jobs, job_qids, seconds = [], [], {}
                for qid, s in state.items():
                    t0 = time.perf_counter()
                    result = s["learner"].prepare(s["labeled"], s["y"][s["labeled"]].tolist())
                    seconds[qid] = time.perf_counter() - t0
                    if result[0] == "scores":
                        s["scores"], s["used"] = result[1], result[2]
                    else:
                        jobs.append(result[1:])
                        job_qids.append(qid)
                if jobs:
                    t0 = time.perf_counter()
                    outputs = tabpfn_batch(model, jobs, max_batch)
                    share = (time.perf_counter() - t0) / len(jobs)
                    for qid, scores in zip(job_qids, outputs):
                        state[qid]["scores"], state[qid]["used"] = scores, True
                        seconds[qid] += share
                for qid, s in state.items():
                    topic = topics[qid]
                    found = int(s["y"][s["labeled"]].sum())
                    total = int(s["y"].sum())
                    pick = acquired[qid]
                    row = {
                        "query_id": qid, "learner": label, "budget": spent, "found": found,
                        "pool_recall": found / total if total else float("nan"),
                        "residual_ndcg_10": residual_ndcg(topic["grades"], s["scores"], s["labeled"]),
                        "update_seconds": seconds[qid], "feedback_used": s.get("used", False),
                        "acquired_doc_id": str(topic["doc_ids"][pick]) if pick is not None else "",
                        "acquired_grade": int(topic["grades"][pick]) if pick is not None else "",
                        # Sum of P(relevant) over unreviewed docs; only meaningful for
                        # probabilistic learners that actually used feedback.
                        "expected_remaining": (float(np.delete(s["scores"], s["labeled"]).sum())
                                               if kind in {"logistic", "lgbm", "tabpfn"} and s.get("used")
                                               else float("nan")),
                        "true_remaining": total - found,
                    }
                    rows.append(row)
                    writer.writerow(row)
                stream.flush()
            found = np.mean([r["found"] for r in rows if r["learner"] == label and r["budget"] == budget])
            print(f"{label}: mean found@{budget} = {found:.2f} "
                  f"({time.perf_counter() - started:.0f}s)", flush=True)
    result = summarize(rows, seed)
    (output / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    print(f"Wrote {output / 'summary.json'}", flush=True)
