"""Lens Feed ranking: label-aware tabular features + TabPFN-3.5, with a similarity baseline.

Two stages, standard for recommenders:
  1. similarity shortlist (Rocchio-style score over unit embeddings) — cheap, all papers;
  2. TabPFN-3.5 scores the shortlist from the paper's embedding plus relational signals
     (similarity to likes/dislikes, shared authors, category overlap, age); context = the
     user's own ratings only. Per the cold-start curve, match scores are shown from
     ``match_after`` ratings (where they beat the user's own like rate), and from then on
     TabPFN also orders the shortlist, so the list is sorted by the score on each card
     (held-out ranking quality is tied with similarity; see README).

TabPFN scores are model estimates of P(like) among papers like those the user rates;
the benchmark measured their calibration among shown papers, not all of arXiv.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import math
import re

import numpy as np

FEATURES = ["sim_like_mean", "sim_like_max", "sim_like_top3", "sim_dislike_mean", "sim_dislike_max",
            "interest_sim", "rocchio", "shared_authors_like", "shared_authors_dislike",
            "primary_cat_like", "primary_cat_dislike", "any_cat_like", "days_old",
            "log_authors", "n_categories", "log_abstract_words", "mentions_code"]
# Compact signal subset appended to the raw embedding ("embsig" — best on the Scholar
# Inbox dev benchmark; shared with lens.feedbench so product and benchmark match).
SIGNALS = ["sim_like_mean", "sim_like_max", "sim_like_top3", "sim_dislike_mean", "sim_dislike_max",
           "rocchio", "shared_authors_like", "shared_authors_dislike", "primary_cat_like",
           "primary_cat_dislike", "days_old"]
# The product omits paper age: dropping it left held-out Brier unchanged (0.191 vs 0.191)
# and removes a train/serve skew for liked papers that are much older than new candidates.
PRODUCT_SIGNALS = [s for s in SIGNALS if s != "days_old"]
CODE = re.compile(r"github\.com|code (is )?(publicly )?available|open[- ]source", re.I)


@dataclass
class Profile:
    likes: list[dict] = field(default_factory=list)      # paper dicts
    dislikes: list[dict] = field(default_factory=list)
    interests: str = ""

    @property
    def labeled(self):
        return self.likes + self.dislikes

    @property
    def labels(self):
        return np.array([1] * len(self.likes) + [0] * len(self.dislikes))


def _rocchio(V, likes_v, dislikes_v, q):
    vec = np.zeros(V.shape[1]) if q is None else q.astype(float).copy()
    if len(likes_v):
        vec = vec + likes_v.mean(axis=0)
    if len(dislikes_v):
        vec = vec - 0.25 * dislikes_v.mean(axis=0)
    norm = np.linalg.norm(vec)
    return V @ (vec / norm) if norm > 0 else np.zeros(len(V))


def similarity_scores(V, profile_v, labels, q):
    """Baseline / stage-1 score: Rocchio over the user's likes, dislikes and interests."""
    return _rocchio(V, profile_v[labels == 1], profile_v[labels == 0], q)


def features(papers, V, profile: Profile, profile_v, q, today: date, self_index=None,
             as_of: list[date] | None = None, groups=None, profile_groups=None):
    """Feature table for ``papers`` relative to the profile.

    ``self_index[i]`` = position of paper i inside the profile (or -1); that profile
    entry is excluded when describing paper i (leave-one-out), so a labeled paper
    never sees its own label.
    ``as_of[i]`` = the date paper i was rated (history rows), so its age is measured
    when the user judged it, not today — otherwise old ratings look like old papers
    (train/serve skew).
    ``groups[i]`` / ``profile_groups[j]``: when equal, profile entry j is hidden from
    paper i (leave-one-day-out). Ratings made in the same session are near-duplicates
    with the same label; letting history rows see them makes training features look
    unlike serving features, where the day's papers are never in the history.
    """
    n, m = len(papers), len(profile.labeled)
    y = profile.labels
    S = V @ profile_v.T if m else np.zeros((n, 0))
    mask = np.ones((n, m), dtype=bool)
    if self_index is not None:
        for i, j in enumerate(self_index):
            if j >= 0:
                mask[i, j] = False
    if groups is not None and profile_groups is not None and m:
        mask &= np.asarray(groups, dtype=object)[:, None] != np.asarray(profile_groups, dtype=object)[None, :]
    like_authors = [set(p["authors"]) for p in profile.labeled]
    out = np.zeros((n, len(FEATURES)), dtype=np.float32)
    for i, p in enumerate(papers):
        pos = mask[i] & (y == 1)
        neg = mask[i] & (y == 0)
        sp, sn = S[i, pos], S[i, neg]
        authors = set(p["authors"])
        cats = set(p["categories"])
        out[i, 0] = sp.mean() if len(sp) else 0
        out[i, 1] = sp.max() if len(sp) else 0
        out[i, 2] = np.sort(sp)[-3:].mean() if len(sp) else 0
        out[i, 3] = sn.mean() if len(sn) else 0
        out[i, 4] = sn.max() if len(sn) else 0
        out[i, 5] = float(V[i] @ q) if q is not None else 0
        roc = (q if q is not None else 0) + (profile_v[pos].mean(0) if pos.any() else 0) \
            - (0.25 * profile_v[neg].mean(0) if neg.any() else 0)
        roc = np.asarray(roc, dtype=float)
        out[i, 6] = float(V[i] @ roc / np.linalg.norm(roc)) if roc.ndim and np.linalg.norm(roc) > 0 else 0
        out[i, 7] = sum(len(authors & like_authors[j]) for j in np.flatnonzero(pos))
        out[i, 8] = sum(len(authors & like_authors[j]) for j in np.flatnonzero(neg))
        liked = [profile.labeled[j] for j in np.flatnonzero(pos)]
        disliked = [profile.labeled[j] for j in np.flatnonzero(neg)]
        out[i, 9] = np.mean([l["primary"] == p["primary"] for l in liked]) if liked else 0
        out[i, 10] = np.mean([d["primary"] == p["primary"] for d in disliked]) if disliked else 0
        out[i, 11] = np.mean([bool(cats & set(l["categories"])) for l in liked]) if liked else 0
        try:
            ref = as_of[i] if as_of is not None else today
            out[i, 12] = (ref - date.fromisoformat(p["created"])).days
        except ValueError:
            out[i, 12] = math.nan
        out[i, 13] = math.log1p(len(p["authors"]))
        out[i, 14] = len(p["categories"])
        out[i, 15] = math.log1p(len(p["abstract"].split()))
        out[i, 16] = float(bool(CODE.search(p["abstract"])))
    return out


def session_groups(profile: Profile, rated: list[date], folds: int = 5) -> list:
    """Groups for leave-one-group-out history features.

    Normally the rating day (same-session ratings are near-duplicates with the same
    label). If ratings span fewer than 3 days — e.g. a new user rating 30 papers in one
    sitting — one day would hide everything, so fall back to ``folds`` contiguous blocks
    in rating order (cross-fitting). Order = likes then dislikes within each day is not
    meaningful, so blocks are formed after sorting by rating date and paper id.
    """
    if len(set(rated)) >= 3:
        return list(rated)
    order = sorted(range(len(rated)), key=lambda i: (rated[i], profile.labeled[i]["id"]))
    groups = [0] * len(rated)
    for rank_, i in enumerate(order):
        groups[i] = f"fold{rank_ * folds // max(len(order), 1)}"
    return groups


@dataclass
class Ranking:
    scores: np.ndarray          # higher = better, for every pool paper
    match: np.ndarray           # model "match" in [0, 1] (nan where not modeled)
    engine: str                 # which model produced the shortlist order
    shortlist: np.ndarray       # pool indices that the model scored
    table: np.ndarray | None = None


class FeedRanker:
    # Thresholds chosen from the cold-start curve (docs/figures/fig_coldstart.png):
    # TabPFN's P(like) beats "your own like rate" from ~30 ratings on dev and test;
    # its ranking only ties similarity ranking from ~50 ratings.
    def __init__(self, engine: str = "tabpfn-fast", device: str = "auto", seed: int = 0,
                 shortlist: int = 600, presumed_negatives: int = 0,
                 match_after: int = 30, min_each: int = 3):
        self.engine, self.device, self.seed = engine, device, seed
        self.shortlist_size, self.presumed = shortlist, presumed_negatives
        self.match_after, self.min_each = match_after, min_each
        self._model = None

    def ready(self, profile: Profile) -> int:
        """Ratings still needed before TabPFN scores and orders the feed (0 = active)."""
        n = len(profile.labeled)
        short = max(0, self.min_each - len(profile.likes)) + max(0, self.min_each - len(profile.dislikes))
        return max(self.match_after - n, short, 0)

    def _tabpfn(self):
        if self._model is None:
            from tabpfn import TabPFNClassifier
            from tabpfn.constants import ModelVersion
            version = ModelVersion.V3_5_FAST if self.engine == "tabpfn-fast" else ModelVersion.V3_5
            self._model = TabPFNClassifier.create_default_for_version(
                version, device=self.device, random_state=self.seed)
        return self._model

    def rank(self, pool, V, profile: Profile, profile_v, q=None, today: date | None = None,
             exclude: set[str] = frozenset()) -> Ranking:
        today = today or date.today()
        y = profile.labels
        stage1 = similarity_scores(V, profile_v, y, q) if (len(y) or q is not None) else np.zeros(len(pool))
        available = np.array([p["id"] not in exclude for p in pool])
        stage1 = np.where(available, stage1, -np.inf)
        order = np.argsort(-stage1, kind="stable")
        if self.engine == "similarity" or self.ready(profile):
            return Ranking(stage1, np.full(len(pool), np.nan), "similarity", order[:0])
        short = order[: min(self.shortlist_size, int(available.sum()))]
        # Context: the user's labels (leave-one-out features) + presumed negatives.
        rated = [date.fromisoformat(p["rated_at"]) if p.get("rated_at") else today
                 for p in profile.labeled]
        X_lab = features(profile.labeled, profile_v, profile, profile_v, q, today,
                         self_index=np.arange(len(y)), as_of=rated,
                         groups=(g := session_groups(profile, rated)), profile_groups=g)
        rng = np.random.default_rng(self.seed + len(y))
        unread = np.flatnonzero(available)
        count = min(self.presumed, len(unread))
        presumed = rng.choice(unread, size=count, replace=False) if count else np.array([], int)
        X_neg = features([pool[i] for i in presumed], V[presumed], profile, profile_v, q, today)
        X_short = features([pool[i] for i in short], V[short], profile, profile_v, q, today)
        # "embsig" input: raw embedding + compact relational signals.
        sig = [FEATURES.index(f) for f in PRODUCT_SIGNALS]
        X_lab = np.hstack([profile_v, X_lab[:, sig]])
        X_neg = np.hstack([V[presumed], X_neg[:, sig]]) if count else np.zeros((0, X_lab.shape[1]))
        X_short = np.hstack([V[short], X_short[:, sig]])
        X_ctx = np.vstack([X_lab, X_neg])
        y_ctx = np.concatenate([y, np.zeros(count, dtype=int)])
        if self.engine == "logistic":
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler().fit(np.nan_to_num(X_ctx))
            model = LogisticRegression(max_iter=2000).fit(scaler.transform(np.nan_to_num(X_ctx)), y_ctx)
            proba = model.predict_proba(scaler.transform(np.nan_to_num(X_short)))[:, 1]
        else:
            model = self._tabpfn()
            model.fit(X_ctx, y_ctx)
            proba = model.predict_proba(X_short)[:, list(model.classes_).index(1)]
        match = np.full(len(pool), np.nan)
        match[short] = proba
        scores = np.full(len(pool), -np.inf)
        # Shortlist ordered by model; everything else stays below in stage-1 order.
        scores[short] = 10.0 + proba
        rest = order[len(short):]
        scores[rest] = np.where(np.isfinite(stage1[rest]), stage1[rest], -np.inf)
        return Ranking(scores, match, self.engine, short, X_short)


def explain(paper: dict, v: np.ndarray, profile: Profile, profile_v: np.ndarray) -> dict:
    """Human-readable reasons: closest liked paper, shared authors, shared categories."""
    reasons = {}
    likes_idx = [j for j, l in enumerate(profile.labeled) if j < len(profile.likes)]
    if likes_idx:
        sims = profile_v[likes_idx] @ v
        j = int(np.argmax(sims))
        reasons["closest_like"] = (profile.likes[j]["title"], float(sims[j]))
    shared = sorted({a for l in profile.likes for a in set(l["authors"]) & set(paper["authors"])})
    if shared:
        reasons["shared_authors"] = shared[:3]
    cats = sorted({c for l in profile.likes for c in set(l["categories"]) & set(paper["categories"])})
    if cats:
        reasons["shared_categories"] = cats[:3]
    return reasons
