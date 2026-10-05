"""Learner specs, identical-feature baselines, and a pinned local TabPFN model.

A spec is ``name`` plus ``+``-separated options, e.g. ``tabpfn+fb+pn50`` or
``rocchio+b1+g0.25`` or ``logistic+fb+pn50+C0.1``:

- ``fb``   add feedback features (similarity to labeled examples, Rocchio score)
- ``pnN``  add N presumed negatives: random *unlabeled* documents temporarily
           labeled non-relevant (BMI/CAL-style; no oracle information, not counted
           as screening cost because no human reviews them)
- ``CX``   logistic inverse regularization strength
- ``bX``/``gX`` Rocchio positive/negative centroid weights
- ``tpN``  add N per-topic PCA components of candidate embeddings (label-free)
- ``nobase`` drop the static query-document feature block (embedding-only view)
- ``mv``   multi-view: add query scores (and, with ``fb``, feedback features) for
           every embedding view in the artifact (e5, bge, medcpt, ...)
- ``v<view>`` Rocchio: which embedding view to use (default e5)
- ``rrf``  Rocchio: reciprocal-rank-fuse its ranking with the frozen cross-encoder
- ``meta`` classifiers: prepend rows from *other topics'* simulated screening sessions
           (see lens/meta.py). Uses only topic-agnostic features: corpus-level PCA
           columns are dropped and session-state columns (labels so far, positives
           so far, positive rate) are added.
- ``rs``   stacking: add the *tuned* Rocchio score (best dev config: bge view if
           present, b=2, g=1) as features, leave-one-out for labeled rows
- ``md``   add CORD-19 document metadata (date, source, venue, license, ...; see
           lens/docmeta.py) on fixed topic-independent scales; NaN = unknown

Learners: static, rocchio, logistic, lgbm (LightGBM), tabpfn.
"""
from __future__ import annotations

import re

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def parse_spec(spec: str):
    name, *opts = spec.split("+")
    if name not in {"static", "logistic", "rocchio", "tabpfn", "lgbm"}:
        raise ValueError(f"Unknown learner {name!r} in {spec!r}")
    options = {"fb": False, "pn": 0, "C": 1.0, "b": 1.0, "g": 0.25, "tp": 0,
               "nobase": False, "mv": False, "rrf": False, "v": "e5", "meta": False, "md": False,
               "rs": False}
    for opt in opts:
        if opt in ("fb", "nobase", "mv", "rrf", "meta", "md", "rs"):
            options[opt] = True
        elif m := re.fullmatch(r"v([a-z][a-z0-9]*)", opt):
            options["v"] = m.group(1)
        elif m := re.fullmatch(r"tp(\d+)", opt):
            options["tp"] = int(m.group(1))
        elif m := re.fullmatch(r"pn(\d+)", opt):
            options["pn"] = int(m.group(1))
        elif m := re.fullmatch(r"([Cbg])([0-9.]+)", opt):
            options[m.group(1)] = float(m.group(2))
        else:
            raise ValueError(f"Unknown option {opt!r} in {spec!r}")
    if name in {"static", "rocchio"} and any(options[k] for k in ("fb", "pn", "tp", "nobase", "mv", "meta", "md", "rs")):
        raise ValueError(f"fb/pn/tp/nobase/mv/meta/md/rs options apply only to classifiers: {spec!r}")
    if options["meta"] and options["tp"]:
        raise ValueError("meta cannot use tp: per-topic PCA axes do not transfer across topics")
    if name != "rocchio" and (options["rrf"] or options["v"] != "e5"):
        raise ValueError(f"v<view>/rrf options apply only to rocchio: {spec!r}")
    return name, options


def rocchio_scores(vectors, query_vector, labeled, labels, beta, gamma):
    vector = query_vector.astype(float).copy()
    y = np.asarray(labels)
    if len(labeled):
        selected = vectors[np.asarray(labeled)]
        if np.any(y == 1):
            vector += beta * selected[y == 1].mean(axis=0)
        if np.any(y == 0):
            vector -= gamma * selected[y == 0].mean(axis=0)
    return vectors @ (vector / max(np.linalg.norm(vector), 1e-12))


def feedback_features(vectors, query_vector, labeled, labels):
    """Similarity to labeled positives/negatives (mean, max) and Rocchio score.

    Leave-one-out: a labeled row never sees its own label. Mean/max columns are
    zero when a class has no (other) labeled example. Rocchio uses default weights.
    """
    labeled = np.asarray(labeled)
    y = np.asarray(labels)
    sims = vectors @ vectors[labeled].T  # (n, L)
    self_mask = np.zeros_like(sims, dtype=bool)
    self_mask[labeled, np.arange(len(labeled))] = True
    columns = []
    for cls in (1, 0):
        use = (y == cls)[None, :] & ~self_mask
        count = use.sum(axis=1)
        mean = np.where(count > 0, (sims * use).sum(axis=1) / np.maximum(count, 1), 0.0)
        best = np.where(count > 0, np.where(use, sims, -np.inf).max(axis=1), 0.0)
        columns += [mean, best]
    roc = rocchio_scores(vectors, query_vector, labeled, labels, 1.0, 0.25)
    # Leave-one-out Rocchio for labeled rows (their own vector removed from centroid).
    for j, i in enumerate(labeled):
        keep = np.arange(len(labeled)) != j
        roc[i] = rocchio_scores(vectors, query_vector, labeled[keep], y[keep], 1.0, 0.25)[i]
    columns.append(roc)
    return np.column_stack(columns)


class RelevanceLearner:
    def __init__(self, spec, topic, *, seed, rng_seed):
        self.spec = spec
        self.name, self.opt = parse_spec(spec)
        self.views = {"e5": (topic["vectors"], topic["query_vector"])}
        for key in topic:
            if key.startswith("vec_"):
                view = key.removeprefix("vec_")
                self.views[view] = (topic[key], topic[f"qvec_{view}"])
        if self.opt["v"] not in self.views:
            raise ValueError(f"View {self.opt['v']!r} not in artifact (have {sorted(self.views)})")
        if self.opt["mv"] and len(self.views) < 2:
            raise ValueError("mv requires an artifact built with `lens add-views`")
        from lens.features import STATIC_COLUMNS
        static = topic["X"][:, :STATIC_COLUMNS] if self.opt["meta"] else topic["X"]
        blocks = [] if self.opt["nobase"] else [static]
        if self.opt["mv"]:
            from lens.features import score_features
            for view in self.views:
                if view != "e5":
                    blocks.append(score_features(topic[f"dense_{view}"].astype(float)))
        if self.opt["tp"]:
            from sklearn.decomposition import PCA
            n = min(self.opt["tp"], *topic["vectors"].shape)
            blocks.append(PCA(n_components=n, random_state=seed).fit_transform(topic["vectors"]))
        if not blocks and not any(self.opt[k] for k in ("fb", "md", "rs")):
            raise ValueError(f"{spec!r} has no features")
        self.X = (StandardScaler().fit_transform(np.column_stack(blocks)) if blocks  # Label-free.
                  else np.zeros((len(topic["base"]), 0)))
        if self.opt["md"]:
            if "docmeta" not in topic:
                raise ValueError("md requires an artifact built with `lens add-metadata`")
            md = topic["docmeta"].astype(float).copy()
            md[:, 0] = (md[:, 0] - 2015) / 5   # year
            md[:, 1] = md[:, 1] / 12           # months since 2020-01
            self.X = np.column_stack([self.X, md])
        self.vectors = topic["vectors"]
        self.query_vector = topic["query_vector"]
        self.base = topic["base"].astype(float)
        self.rng = np.random.default_rng(rng_seed)  # presumed-negative sampling only
        self.seed = seed
        self.meta = None  # (X, y) from other topics' sessions, set by the evaluator

    def features(self, labeled, labels):
        """Full feature matrix for every candidate given the session's labels so far."""
        X = self.X
        if self.opt["fb"] and len(labeled):
            views = self.views.items() if self.opt["mv"] else [("e5", self.views["e5"])]
            extra = np.column_stack([feedback_features(v, q, labeled, labels) for _, (v, q) in views])
            extra = (extra - extra.mean(axis=0)) / np.maximum(extra.std(axis=0), 1e-8)
            X = np.column_stack([X, extra])
        elif self.opt["fb"]:
            width = 5 * (len(self.views) if self.opt["mv"] else 1)
            X = np.column_stack([X, np.zeros((len(X), width))])
        if self.opt["rs"]:
            from lens.features import score_features
            vectors, query = self.views["bge" if "bge" in self.views else "e5"]
            lab, y = np.asarray(labeled, dtype=int), np.asarray(labels)
            roc = rocchio_scores(vectors, query, lab, y, 2.0, 1.0)
            for j, i in enumerate(lab):  # leave-one-out for labeled rows
                keep = np.arange(len(lab)) != j
                roc[i] = rocchio_scores(vectors, query, lab[keep], y[keep], 2.0, 1.0)[i]
            X = np.column_stack([X, score_features(roc)])
        if self.opt["meta"]:
            k, pos = len(labeled), int(np.sum(labels)) if len(labeled) else 0
            X = np.column_stack([X, np.tile([k, pos, pos / max(k, 1)], (len(X), 1))])
        return X

    def prepare(self, labeled, labels):
        """Return ("scores", scores, used) or ("fit", X_train, y_train, X_all).

        Classifiers without both classes in their context fall back to the frozen
        ranking. No hidden oracle seeding; presumed negatives are unlabeled docs.
        """
        if self.name == "static" or len(labeled) == 0:
            return ("scores", self.base.copy(), False)
        if self.name == "rocchio":
            vectors, query = self.views[self.opt["v"]]
            scores = rocchio_scores(vectors, query, labeled, labels, self.opt["b"], self.opt["g"])
            if self.opt["rrf"]:
                def ranks(s):
                    return np.argsort(np.argsort(-s, kind="stable"), kind="stable")
                scores = 1 / (61 + ranks(scores)) + 1 / (61 + ranks(self.base))
            return ("scores", scores, True)
        X = self.features(labeled, labels)
        rows, y = list(labeled), list(labels)
        if self.opt["pn"]:
            unlabeled = np.setdiff1d(np.arange(len(self.base)), labeled)
            count = min(self.opt["pn"], len(unlabeled))
            rows += self.rng.choice(unlabeled, size=count, replace=False).tolist()
            y += [0] * count
        X_train, y_train = X[rows], np.asarray(y)
        if self.opt["meta"]:
            if self.meta is None:
                raise RuntimeError("meta learner has no past-session context")
            X_train = np.vstack([self.meta[0], X_train])
            y_train = np.concatenate([self.meta[1], y_train])
        if len(set(y_train.tolist())) < 2:
            return ("scores", self.base.copy(), False)
        if self.name == "logistic":
            model = LogisticRegression(C=self.opt["C"], max_iter=5000, random_state=self.seed)
            model.fit(np.nan_to_num(X_train), y_train)  # zero = mean/unknown imputation
            return ("scores", model.predict_proba(np.nan_to_num(X))[:, list(model.classes_).index(1)], True)
        if self.name == "lgbm":
            from lightgbm import LGBMClassifier
            model = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15,
                                   min_child_samples=5, subsample=0.8, subsample_freq=1,
                                   colsample_bytree=0.8, random_state=self.seed, verbose=-1,
                                   n_jobs=4)
            model.fit(X_train, y_train)
            return ("scores", model.predict_proba(X)[:, list(model.classes_).index(1)], True)
        return ("fit", X_train.astype(np.float32), y_train, X.astype(np.float32))


def make_tabpfn(*, seed, device, version, estimators):
    try:
        from tabpfn import TabPFNClassifier
        from tabpfn.constants import ModelVersion
    except ImportError as exc:
        raise RuntimeError("Install TabPFN: uv sync --extra tabpfn") from exc
    model_version = ModelVersion.V3_5 if version == "3.5" else ModelVersion.V3_5_FAST
    return TabPFNClassifier.create_default_for_version(
        model_version, device=device, random_state=seed, n_estimators=estimators,
    )


def tabpfn_batch(model, jobs, max_batch=None):
    """Score several independent (X_train, y_train, X_all) jobs with one fused pass.

    Test sets are padded to a common length by repeating rows; test rows attend only
    to training rows, so padding does not change real-row predictions. Jobs are
    grouped by training shape (required by predict_proba_batched).
    """
    results = [None] * len(jobs)
    groups: dict[tuple, list[int]] = {}
    for k, (Xtr, _, _) in enumerate(jobs):
        groups.setdefault(Xtr.shape, []).append(k)
    chunks = []
    for members in groups.values():
        step = max_batch or len(members)
        chunks += [members[i:i + step] for i in range(0, len(members), step)]
    for members in chunks:
        width = max(len(jobs[k][2]) for k in members)
        tests = []
        for k in members:
            Xall = jobs[k][2]
            pad = np.repeat(Xall[:1], width - len(Xall), axis=0)
            tests.append(np.vstack([Xall, pad]))
        proba = model.predict_proba_batched(
            [jobs[k][0] for k in members], [jobs[k][1] for k in members], tests,
        )
        for slot, k in enumerate(members):
            results[k] = proba[slot, : len(jobs[k][2]), 1]
    return results
