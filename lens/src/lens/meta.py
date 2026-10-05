"""Past-session context tables for ``meta`` learners.

For each *training* topic we simulate a screening session (frozen ranker for the
initial labels, then greedy Rocchio in the e5 view) and snapshot it at several
budgets. At each snapshot we emit rows for the labeled documents (leave-one-out
feedback features) and for a sample of unlabeled ones: the top of the current
Rocchio ranking (where a greedy screener actually looks) plus random documents.
Targets are the training topic's true judgments — standing in for the labels
earlier users produced. Evaluated topics are never in their own context table.
"""
from __future__ import annotations

import hashlib

import numpy as np

from lens.learners import RelevanceLearner, rocchio_scores

SNAPSHOTS = (2, 5, 10, 15, 20, 25, 30)


def build_table(topics: dict, spec: str, *, relevant_grade: int, seed: int, initial: int = 2,
                top: int = 60, random_rows: int = 30, max_rows: int = 10000):
    blocks, targets = [], []
    for qid, topic in sorted(topics.items()):
        topic_seed = (seed + int(hashlib.sha256(f"meta:{qid}".encode()).hexdigest()[:8], 16)) % (2**32)
        rng = np.random.default_rng(topic_seed)
        learner = RelevanceLearner(spec, topic, seed=seed, rng_seed=topic_seed)
        y = (topic["grades"] >= relevant_grade).astype(int)
        order = np.argsort(-topic["base"], kind="stable")
        labeled = [int(i) for i in order[:initial]]
        for budget in range(initial, max(SNAPSHOTS) + 1):
            if budget > len(labeled):
                scores = rocchio_scores(topic["vectors"], topic["query_vector"], labeled,
                                        y[labeled].tolist(), 1.0, 0.25)
                scores[labeled] = -np.inf
                labeled.append(int(np.argmax(scores)))
            if budget not in SNAPSHOTS:
                continue
            X = learner.features(labeled, y[labeled].tolist())
            scores = rocchio_scores(topic["vectors"], topic["query_vector"], labeled,
                                    y[labeled].tolist(), 1.0, 0.25)
            scores[labeled] = -np.inf
            unlabeled = np.setdiff1d(np.arange(len(y)), labeled)
            near = np.argsort(-scores, kind="stable")[:top]
            far = rng.choice(np.setdiff1d(unlabeled, near), size=min(random_rows, len(unlabeled) - top),
                             replace=False)
            rows = np.concatenate([labeled, near, far]).astype(int)
            blocks.append(X[rows])
            targets.append(y[rows])
    X, y = np.vstack(blocks), np.concatenate(targets)
    if len(y) > max_rows:
        keep = np.random.default_rng(seed).choice(len(y), size=max_rows, replace=False)
        X, y = X[np.sort(keep)], y[np.sort(keep)]
    return X.astype(np.float32), y


def folds(qids, k):
    """Deterministic topic folds (by sorted id) for leave-topics-out context."""
    ordered = sorted(qids, key=lambda q: hashlib.sha256(q.encode()).hexdigest())
    return {q: i % k for i, q in enumerate(ordered)}
