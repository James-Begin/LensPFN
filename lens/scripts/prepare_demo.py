"""Prepare a separate, public-data Lens profile for an optional local demo."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from lens.feed.rank import Profile
from lens.feed.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".lens-feed-demo"))
    parser.add_argument("--limit", type=int, default=300,
                        help="Number of public cs.LG/stat.ML candidates; 0 loads the full week.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative.")
    if args.root.exists():
        parser.error(f"{args.root} already exists. Choose a new --root; existing profiles are never replaced.")
    data = Path(__file__).resolve().parents[1] / "src/lens/feed/demo"
    persona = json.loads((data / "persona-prior-labs.json").read_text())
    with gzip.open(data / "pool-2026-09-25-2026-10-02.json.gz", "rt") as file:
        pool = json.load(file)
    if args.limit:
        rated = {paper["id"] for paper in persona["likes"] + persona["dislikes"]}
        pool = sorted((paper for paper in pool if paper["id"] not in rated and
                       {"cs.LG", "stat.ML"}.intersection(paper["categories"])),
                      key=lambda paper: (paper["created"], paper["id"]), reverse=True)[:args.limit]
    store = Store(args.root)
    store.save_profile(Profile(likes=persona["likes"], dislikes=persona["dislikes"],
                               interests=persona["interests"]), set(persona["hidden"]))
    (args.root / "pool-demo-2026-09-25-2026-10-02.json").write_text(json.dumps(pool))
    print(f"Prepared {args.root}: 29 Interested, 15 Not for me, {len(pool):,} public candidates.")
    print("These are illustrative persona ratings, not your personal history or benchmark users.")
    print(f"Start: uv run --no-sync python -m lens.feed.bridge --root {args.root} --device cpu")


if __name__ == "__main__":
    main()

