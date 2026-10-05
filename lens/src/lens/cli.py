"""Reproducible experiment commands; no hosted inference or credential mutation."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


def main():
    parser = argparse.ArgumentParser(description="Lens relevance-feedback feasibility experiment")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Download judged data and cache label-free features")
    prepare.add_argument("--cache", type=Path, default=Path(".cache/data"))
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--topics", type=int, default=6)
    prepare.add_argument("--split", choices=["dev", "test"], default="dev")
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--pool-size", type=int, default=0, help="0 = full judged pool per topic")
    prepare.add_argument("--features", choices=["semantic", "lexical"], default="semantic")
    prepare.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    prepare.add_argument("--dev-fraction", type=float, default=0.2,
                         help="fraction of topics in the dev split (fixed before any test run)")
    views = commands.add_parser("add-views", help="Add extra embedding views to a feature artifact")
    views.add_argument("--source", type=Path, required=True)
    views.add_argument("--output", type=Path, required=True)
    views.add_argument("--views", nargs="+", default=["bge", "medcpt"])
    views.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    bprep = commands.add_parser("bench-prepare", help="Build the Lens Feed benchmark (Scholar Inbox)")
    bprep.add_argument("--ratings", type=Path, required=True, help="scholar_inbox_datasets/data/rated_papers.csv")
    bprep.add_argument("--output", type=Path, required=True)
    bprep.add_argument("--users", type=int, default=240)
    bprep.add_argument("--seed", type=int, default=42)
    bprep.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    brun = commands.add_parser("bench-run", help="Prequential replay of the Lens Feed benchmark")
    brun.add_argument("--bench", type=Path, required=True)
    brun.add_argument("--output", type=Path, required=True)
    brun.add_argument("--learners", nargs="+", required=True,
                      help="view:model, e.g. rocchio:g0.25 emb:logistic+C1 feat:tabpfn featemb:lgbm")
    brun.add_argument("--split", choices=["dev", "test"], default="dev")
    brun.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    brun.add_argument("--max-days", type=int, default=30)
    brun.add_argument("--user-shard", default="0/1", help="k/n: run every n-th user starting at k")
    brun.add_argument("--no-lodo", action="store_true",
                      help="ablation: history features may see same-day ratings")
    bcold = commands.add_parser("bench-coldstart", help="Cold-start curve: quality vs number of ratings")
    bcold.add_argument("--bench", type=Path, required=True)
    bcold.add_argument("--output", type=Path, required=True)
    bcold.add_argument("--learners", nargs="+", required=True)
    bcold.add_argument("--split", choices=["dev", "test"], default="dev")
    bcold.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    bcold.add_argument("--user-shard", default="0/1")
    meta = commands.add_parser("add-metadata", help="Add CORD-19 document metadata features")
    meta.add_argument("--source", type=Path, required=True)
    meta.add_argument("--output", type=Path, required=True)
    meta.add_argument("--cache", type=Path, default=Path(".cache/data"))
    evaluate = commands.add_parser("evaluate", help="Run budget-accounted simulated relevance feedback")
    evaluate.add_argument("--features", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--learners", nargs="+",
                          default=["static", "logistic", "rocchio", "tabpfn"],
                          help="learner specs, e.g. rocchio+b1+g0.25 tabpfn+fb+pn50 (see lens/learners.py)")
    evaluate.add_argument("--budget", type=int, default=20)
    evaluate.add_argument("--initial", type=int, default=2)
    evaluate.add_argument("--policy", choices=["greedy", "passive", "random"], default="greedy")
    evaluate.add_argument("--seed", type=int, default=42)
    evaluate.add_argument("--device", choices=["cpu", "mps", "cuda", "auto"], default="cpu")
    evaluate.add_argument("--tabpfn-version", choices=["3.5", "3.5-fast"], default="3.5")
    evaluate.add_argument("--estimators", default="auto", help="auto for checkpoint defaults, or positive integer")
    evaluate.add_argument("--relevant-grade", type=int, choices=[1, 2], default=2,
                          help="2 = highly relevant only (primary); 1 = any relevance")
    evaluate.add_argument("--meta-features", type=Path, default=None,
                          help="artifact whose topics supply past-session context (must not overlap)")
    evaluate.add_argument("--meta-folds", type=int, default=4,
                          help="leave-topics-out folds when --meta-features is not given")
    evaluate.add_argument("--max-batch", type=int, default=None,
                          help="max topics per batched TabPFN call (limits GPU memory)")
    commands.add_parser("doctor", help="Inspect local dependencies and model support without downloading weights")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from lens.features import prepare as run
            run(cache=args.cache, output=args.output, topics=args.topics, split=args.split,
                seed=args.seed, pool_size=args.pool_size, mode=args.features, device=args.device,
                dev_fraction=args.dev_fraction)
        elif args.command == "add-views":
            from lens.views import add_views
            add_views(source=args.source, output=args.output, views=args.views, device=args.device)
        elif args.command == "bench-prepare":
            from lens.feedbench import prepare as bench_prepare
            bench_prepare(ratings_csv=args.ratings, output=args.output, users=args.users,
                          seed=args.seed, device=args.device)
        elif args.command == "bench-run":
            from lens.feedbench import run as bench_run
            bench_run(bench=args.bench, output=args.output, learners=args.learners, split=args.split,
                      device=args.device, max_days=args.max_days, user_shard=args.user_shard,
                      lodo=not args.no_lodo)
        elif args.command == "bench-coldstart":
            from lens.feedbench import coldstart
            coldstart(bench=args.bench, output=args.output, learners=args.learners,
                      split=args.split, device=args.device, user_shard=args.user_shard)
        elif args.command == "add-metadata":
            from lens.docmeta import add_metadata
            add_metadata(source=args.source, output=args.output, cache=args.cache)
        elif args.command == "evaluate":
            estimators = "auto" if args.estimators == "auto" else int(args.estimators)
            if estimators != "auto" and estimators < 1:
                raise ValueError("--estimators must be auto or positive")
            from lens.evaluate import evaluate as run
            run(features=args.features, output=args.output, names=args.learners, budget=args.budget,
                initial=args.initial, policy=args.policy, seed=args.seed, device=args.device,
                version=args.tabpfn_version, estimators=estimators,
                relevant_grade=args.relevant_grade, meta_features=args.meta_features,
                meta_folds=args.meta_folds, max_batch=args.max_batch)
        else:
            report = {"python": sys.version.split()[0], "architecture": platform.machine(), "packages": {}}
            for name in ["numpy", "scikit-learn", "tabpfn", "sentence-transformers"]:
                try:
                    report["packages"][name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    report["packages"][name] = "not installed"
            if report["packages"]["tabpfn"] != "not installed":
                import torch
                from tabpfn.constants import ModelVersion
                report["tabpfn_versions"] = [item.value for item in ModelVersion]
                report["mps_available"] = torch.backends.mps.is_available()
                report["cuda_available"] = torch.cuda.is_available()
            print(json.dumps(report, indent=2))
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(2, f"lens: {exc}\n")


if __name__ == "__main__":
    main()
