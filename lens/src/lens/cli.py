"""Reproducible experiment commands; no hosted inference or credential mutation."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


def main():
    parser = argparse.ArgumentParser(description="Lens paper-interest benchmark and dependency diagnostics")
    commands = parser.add_subparsers(dest="command", required=True)
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
    commands.add_parser("doctor", help="Inspect local dependencies and model support without downloading weights")
    args = parser.parse_args()
    try:
        if args.command == "bench-prepare":
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
