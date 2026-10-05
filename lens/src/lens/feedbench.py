"""Offline benchmark for Lens Feed on Scholar Inbox ratings (explicit 👍/👎 on arXiv papers).

Data: https://github.com/avg-dev/scholar_inbox_datasets (CC BY-NC-ND 4.0 — evaluation
only; never shipped in the product or redistributed). Paper text/authors/categories
from the CC0 arXiv metadata snapshot (librarian-bots/arxiv-metadata-snapshot).

Protocol (prequential replay, identical history for every learner):
  * users split into disjoint dev/test groups (seeded);
  * per user, ratings sorted by time, capped to the first MAX_RATINGS; ratings before
    the 30% time-quantile are onboarding history;
  * each later calendar day: every learner scores the papers the user rated that day
    using only earlier ratings; afterwards that day's ratings join the history.
Caveat: negatives are papers Scholar Inbox's own ranker chose to show (exposure bias),
so this measures re-ranking among shown papers, not discovery from the whole arXiv.
"""
from __future__ import annotations

from datetime import date
from email.utils import parsedate_to_datetime
import glob
import json
import math
import os
from pathlib import Path
import time

import numpy as np

from lens.feed.rank import FEATURES, SIGNALS, Profile, features

MAX_RATINGS = 300
SNAPSHOT = "librarian-bots/arxiv-metadata-snapshot"


def _created(versions):
    try:
        return parsedate_to_datetime(versions[0]["created"]).date().isoformat()
    except (TypeError, ValueError, IndexError, KeyError):
        return ""


def prepare(*, ratings_csv: Path, output: Path, users: int, seed: int, device: str,
            min_pos: int = 20, min_neg: int = 20, min_days: int = 8):
    import pandas as pd
    import pyarrow.parquet as pq
    from huggingface_hub import snapshot_download

    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty")
    r = pd.read_csv(ratings_csv, dtype={"arxiv_id": str})
    r["time"] = pd.to_datetime(r["time"], format="mixed", errors="coerce")
    r = r.dropna(subset=["time"]).sort_values(["user_id", "time"])
    r = r.groupby("user_id", group_keys=False).head(MAX_RATINGS)
    stats = r.groupby("user_id").agg(pos=("rating", lambda x: (x > 0).sum()),
                                     neg=("rating", lambda x: (x < 0).sum()),
                                     days=("time", lambda t: t.dt.date.nunique()))
    eligible = stats[(stats.pos >= min_pos) & (stats.neg >= min_neg) & (stats.days >= min_days)].index
    rng = np.random.default_rng(seed)
    chosen = rng.choice(np.array(sorted(eligible)), size=min(users, len(eligible)), replace=False)
    split = {int(u): ("dev" if k % 2 == 0 else "test") for k, u in enumerate(chosen)}
    r = r[r.user_id.isin(split)]
    needed = set(r.arxiv_id)
    print(f"{len(eligible)} eligible users; chose {len(split)}; {len(needed)} papers needed", flush=True)

    local = snapshot_download(SNAPSHOT, repo_type="dataset",
                              cache_dir=os.path.expanduser("~/.cache/huggingface/lens"))
    papers = {}
    cols = ["id", "title", "abstract", "authors_parsed", "categories", "versions"]
    for shard in sorted(glob.glob(f"{local}/data/*.parquet")):
        table = pq.read_table(shard, columns=cols)
        ids = table.column("id").to_pylist()
        keep = [i for i, x in enumerate(ids) if x in needed]
        for row in table.take(keep).to_pylist():
            authors = [" ".join(x for x in (a[1], a[0]) if x).strip() for a in (row["authors_parsed"] or [])]
            cats = (row["categories"] or "").split()
            papers[row["id"]] = {
                "id": row["id"], "title": " ".join((row["title"] or "").split()),
                "abstract": " ".join((row["abstract"] or "").split()),
                "authors": [a for a in authors if a], "categories": cats,
                "primary": cats[0] if cats else "", "created": _created(row["versions"]),
            }
        print(f"{Path(shard).name}: {len(papers)}/{len(needed)} papers found", flush=True)
    r = r[r.arxiv_id.isin(papers)]
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/e5-small-v2", device=device)
    order = sorted(papers)
    vectors = model.encode([f"passage: {papers[i]['title']}. {papers[i]['abstract']}" for i in order],
                           batch_size=256, normalize_embeddings=True, show_progress_bar=False)
    output.mkdir(parents=True)
    np.savez(output / "vectors.npz", ids=np.array(order), vectors=vectors.astype(np.float32))
    (output / "papers.json").write_text(json.dumps(papers))
    r.assign(split=r.user_id.map(split)).to_csv(output / "ratings.csv", index=False)
    (output / "manifest.json").write_text(json.dumps({
        "ratings_source": "https://github.com/avg-dev/scholar_inbox_datasets (CC BY-NC-ND 4.0)",
        "metadata_source": f"hf://datasets/{SNAPSHOT} (CC0)", "seed": seed,
        "users": {"dev": sum(v == "dev" for v in split.values()),
                  "test": sum(v == "test" for v in split.values())},
        "eligibility": {"min_pos": min_pos, "min_neg": min_neg, "min_days": min_days,
                        "max_ratings": MAX_RATINGS},
        "papers": len(papers), "ratings": int(len(r)), "encoder": "intfloat/e5-small-v2",
    }, indent=2))
    print(f"Wrote {output}: {len(r)} ratings, {len(papers)} papers", flush=True)


# ---------------------------------------------------------------- learners

def _fit_predict(learner, X_hist, y_hist, X_pool, state):
    name, _, opt = learner.partition("+")
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        sc = StandardScaler().fit(np.nan_to_num(X_hist))
        C = float(opt.removeprefix("C")) if opt.startswith("C") else 1.0
        m = LogisticRegression(C=C, max_iter=3000).fit(sc.transform(np.nan_to_num(X_hist)), y_hist)
        return m.predict_proba(sc.transform(np.nan_to_num(X_pool)))[:, 1]
    if name == "logcal":  # logistic + per-user cross-validated Platt calibration (sklearn standard)
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        C = float(opt.removeprefix("C")) if opt.startswith("C") else 1.0
        folds = int(min(3, np.bincount(y_hist, minlength=2).min()))
        base = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000))
        if folds < 2:  # too few of a class to cross-validate: plain logistic
            return base.fit(np.nan_to_num(X_hist), y_hist).predict_proba(np.nan_to_num(X_pool))[:, 1]
        m = CalibratedClassifierCV(base, method="sigmoid", cv=folds)
        return m.fit(np.nan_to_num(X_hist), y_hist).predict_proba(np.nan_to_num(X_pool))[:, 1]
    if name == "lgbm":
        from lightgbm import LGBMClassifier
        m = LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=5,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=4)
        return m.fit(X_hist, y_hist).predict_proba(X_pool)[:, 1]
    if name in ("tabpfn", "tabpfnfast"):
        if "model" not in state:
            from tabpfn import TabPFNClassifier
            from tabpfn.constants import ModelVersion
            v = ModelVersion.V3_5_FAST if name == "tabpfnfast" else ModelVersion.V3_5
            state["model"] = TabPFNClassifier.create_default_for_version(
                v, device=state["device"], random_state=0)
        m = state["model"].fit(X_hist, y_hist)
        return m.predict_proba(X_pool)[:, list(m.classes_).index(1)]
    raise ValueError(learner)


def _rocplatt(PV, yo, days, VV, g):
    """Platt-calibrated Rocchio: monotone, so ranking (AUC) equals Rocchio's.

    History scores are cross-fitted (each row scored by a centroid built from other
    rating days, or from 5 rating-order blocks when there are < 3 days), then a 1-D
    logistic map is fit. A non-positive slope falls back to the base rate while
    keeping Rocchio's order, so ranking always equals Rocchio's.
    """
    from sklearn.linear_model import LogisticRegression
    days = list(days)
    if len(set(days)) >= 3:
        groups = np.array([str(d) for d in days])
    else:
        groups = np.array([f"b{i * 5 // len(days)}" for i in range(len(days))])
    def centroid(mask):
        pos, neg = PV[mask & (yo == 1)], PV[mask & (yo == 0)]
        c = (pos.mean(0) if len(pos) else 0) - g * (neg.mean(0) if len(neg) else 0)
        c = np.asarray(c, dtype=float)
        return c / max(np.linalg.norm(c), 1e-12) if c.ndim else np.zeros(PV.shape[1])
    hist = np.zeros(len(yo))
    for grp in set(groups):
        inside = groups == grp
        hist[inside] = PV[inside] @ centroid(~inside)
    pool = VV @ centroid(np.ones(len(yo), dtype=bool))
    mu, sd = hist.mean(), max(hist.std(), 1e-9)  # standardize the 1-D score (Platt practice)
    zh, zp = (hist - mu) / sd, (pool - mu) / sd
    m = LogisticRegression(C=1.0, max_iter=1000).fit(zh[:, None], yo)
    tie_break = 1e-7 * zp  # keeps Rocchio's order exactly even where probabilities saturate
    if m.coef_[0, 0] <= 0:  # no usable calibration signal: base rate, keep Rocchio's order
        return yo.mean() + 1e3 * tie_break
    return np.clip(m.predict_proba(zp[:, None])[:, 1], 1e-6, 1 - 1e-6) + tie_break


def coldstart(*, bench: Path, output: Path, learners: list[str], split: str, device: str,
              ks=(2, 4, 6, 8, 10, 15, 20, 30, 50), eval_fraction: float = 0.4,
              max_eval: int = 60, user_shard: str = "0/1"):
    """Cold-start curve: model quality as a function of history size k.

    Per user: fixed evaluation set = final ``eval_fraction`` of ratings by time (capped
    to the first ``max_eval`` of those); history = the k ratings immediately before it,
    with no updating. Same evaluation set for every k and learner. A (user, k) cell is
    scored only if its history has at least one like and one dislike and the user has
    k ratings before the evaluation window. Views: rocchio, emb, embsig.
    """
    import pandas as pd
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty")
    papers = json.loads((bench / "papers.json").read_text())
    with np.load(bench / "vectors.npz", allow_pickle=False) as d:
        vec = dict(zip(d["ids"].tolist(), d["vectors"]))
    r = pd.read_csv(bench / "ratings.csv", dtype={"arxiv_id": str}, parse_dates=["time"])
    r = r[r.split == split]
    k_, n_ = map(int, user_shard.split("/"))
    users = sorted(r.user_id.unique())[k_::n_]
    output.mkdir(parents=True)
    (output / "config.json").write_text(json.dumps({
        "bench": str(bench), "learners": learners, "split": split, "ks": list(ks),
        "eval_fraction": eval_fraction, "max_eval": max_eval, "user_shard": user_shard,
        "history_features": "leave-one-day-out, rating-date ages"}, indent=2))
    state = {"device": device}
    sig = [FEATURES.index(f) for f in SIGNALS]
    with (output / "predictions.csv").open("w") as out:
        out.write("user_id,k,arxiv_id,label,learner,score\n")
        for u_i, u in enumerate(users):
            ur = r[r.user_id == u].sort_values("time").reset_index(drop=True)
            split_at = int(round(len(ur) * (1 - eval_fraction)))
            ev = ur.iloc[split_at: split_at + max_eval]
            before = ur.iloc[:split_at]
            ev_ids, ev_y = list(ev.arxiv_id), (ev.rating > 0).astype(int).to_numpy()
            ev_days = list(ev.time.dt.date)
            VV = np.stack([vec[i] for i in ev_ids])
            pool = [papers[i] for i in ev_ids]
            for k in ks:
                if k > len(before):
                    continue
                h = before.iloc[-k:]
                hy = (h.rating > 0).astype(int).to_numpy()
                if hy.min() == hy.max():
                    continue
                likes = [(i, d) for i, d, l in zip(h.arxiv_id, h.time.dt.date, hy) if l]
                dislikes = [(i, d) for i, d, l in zip(h.arxiv_id, h.time.dt.date, hy) if not l]
                prof = Profile(likes=[papers[i] for i, _ in likes], dislikes=[papers[i] for i, _ in dislikes])
                order = likes + dislikes
                days = [d for _, d in order]
                yo = np.array([1] * len(likes) + [0] * len(dislikes))
                PV = np.stack([vec[i] for i, _ in order])
                F_h = F_p = None
                for spec in learners:
                    view, _, model = spec.partition(":")
                    if view == "prior":  # trivial baseline: user's own (Laplace) like rate
                        score = np.full(len(ev_ids), (yo.sum() + 1) / (len(yo) + 2))
                    elif view == "rocchio":
                        g = float(model.removeprefix("g")) if model else 0.25
                        c = PV[yo == 1].mean(0) - g * PV[yo == 0].mean(0)
                        score = VV @ (c / max(np.linalg.norm(c), 1e-12))
                    else:
                        if view == "embsig" and F_h is None:
                            F_h = features(prof.labeled, PV, prof, PV, None, ev_days[0],
                                           self_index=np.arange(len(yo)), as_of=days,
                                           groups=days, profile_groups=days)
                            F_p = features(pool, VV, prof, PV, None, ev_days[0], as_of=ev_days)
                        if view == "emb":
                            Xh, Xp = PV, VV
                        elif view == "embsig":
                            Xh, Xp = np.hstack([PV, F_h[:, sig]]), np.hstack([VV, F_p[:, sig]])
                        else:
                            raise ValueError(f"coldstart supports rocchio/emb/embsig views, got {spec!r}")
                        score = _fit_predict(model, Xh, yo, Xp, state)
                    for pid, lab, s in zip(ev_ids, ev_y, score):
                        out.write(f"{u},{k},{pid},{lab},{spec},{float(s):.10g}\n")
            out.flush()
            print(f"user {u_i + 1}/{len(users)} done", flush=True)
    print(f"Wrote {output}", flush=True)


def run(*, bench: Path, output: Path, learners: list[str], split: str, device: str,
        max_days: int = 30, history_fraction: float = 0.3, user_shard: str = "0/1",
        lodo: bool = True):
    """learner spec = <view>:<model>, view in {feat, sig, roc, emb, embsig, featemb, rocchio}
    (roc = the Rocchio-score feature alone, so roc:logistic is Platt-calibrated Rocchio); e.g.
    feat:tabpfn  emb:logistic+C1  featemb:tabpfnfast  rocchio:g0.25"""
    import pandas as pd
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty")
    papers = json.loads((bench / "papers.json").read_text())
    with np.load(bench / "vectors.npz", allow_pickle=False) as d:
        vec = dict(zip(d["ids"].tolist(), d["vectors"]))
    r = pd.read_csv(bench / "ratings.csv", dtype={"arxiv_id": str}, parse_dates=["time"])
    r = r[r.split == split]
    k, n = map(int, user_shard.split("/"))
    users = sorted(r.user_id.unique())[k::n]
    pca = None
    if any(s.startswith("featemb") for s in learners):
        from sklearn.decomposition import PCA  # label-free, fit on all bench papers
        ids = sorted(vec)
        pca = PCA(n_components=32, random_state=0).fit(np.stack([vec[i] for i in ids]))
    output.mkdir(parents=True)
    (output / "config.json").write_text(json.dumps({
        "bench": str(bench), "learners": learners, "split": split, "users": len(users),
        "max_days": max_days, "history_fraction": history_fraction, "user_shard": user_shard,
        "leave_one_day_out_history_features": lodo,
        "features": FEATURES}, indent=2))
    state = {"device": device}
    sig = [FEATURES.index(f) for f in SIGNALS]
    sig_noage = [FEATURES.index(f) for f in SIGNALS if f != "days_old"]
    timing = {s: 0.0 for s in learners}
    with (output / "predictions.csv").open("w") as out:
        out.write("user_id,day,arxiv_id,label,learner,score\n")
        for u_i, u in enumerate(users):
            ur = r[r.user_id == u].sort_values("time")
            cutoff = ur.time.quantile(history_fraction)
            hist = ur[ur.time <= cutoff]
            future = ur[ur.time > cutoff]
            days = sorted(future.time.dt.date.unique())[:max_days]
            hist_ids, hist_y = list(hist.arxiv_id), list((hist.rating > 0).astype(int))
            hist_days = list(hist.time.dt.date)
            for day in days:
                today = ur[(ur.time > cutoff) & (ur.time.dt.date == day)]
                pool_ids, pool_y = list(today.arxiv_id), list((today.rating > 0).astype(int))
                y = np.array(hist_y)
                if len(set(hist_y)) == 2 and pool_ids:
                    prof = Profile(likes=[papers[i] for i, l in zip(hist_ids, hist_y) if l],
                                   dislikes=[papers[i] for i, l in zip(hist_ids, hist_y) if not l])
                    order = [i for i, l in zip(hist_ids, hist_y) if l] + [i for i, l in zip(hist_ids, hist_y) if not l]
                    order_days = [d for d, l in zip(hist_days, hist_y) if l] + [d for d, l in zip(hist_days, hist_y) if not l]
                    yo = np.array([1] * len(prof.likes) + [0] * len(prof.dislikes))
                    PV = np.stack([vec[i] for i in order])
                    VV = np.stack([vec[i] for i in pool_ids])
                    pool = [papers[i] for i in pool_ids]
                    F_h = F_p = None
                    for spec in learners:
                        t0 = time.perf_counter()
                        view, _, model = spec.partition(":")
                        if view == "prior":  # trivial baseline: user's own (Laplace) like rate
                            score = np.full(len(pool_ids), (yo.sum() + 1) / (len(yo) + 2))
                        elif view == "rocplatt":
                            g = float(model.removeprefix("g")) if model else 0.5
                            score = _rocplatt(PV, yo, order_days, VV, g)
                        elif view == "rocchio":
                            g = float(model.removeprefix("g")) if model else 0.25
                            c = PV[yo == 1].mean(0) - g * PV[yo == 0].mean(0)
                            score = VV @ (c / max(np.linalg.norm(c), 1e-12))
                        else:
                            if view in ("feat", "featemb", "sig", "embsig", "embsignoage", "roc") and F_h is None:
                                F_h = features(prof.labeled, PV, prof, PV, None, day,
                                               self_index=np.arange(len(yo)), as_of=order_days,
                                               groups=order_days if lodo else None,
                                               profile_groups=order_days if lodo else None)
                                F_p = features(pool, VV, prof, PV, None, day)
                            if view == "feat":
                                Xh, Xp = F_h, F_p
                            elif view == "emb":
                                Xh, Xp = PV, VV
                            elif view == "roc":
                                c = FEATURES.index("rocchio")
                                Xh, Xp = F_h[:, [c]], F_p[:, [c]]
                            elif view == "sig":
                                Xh, Xp = F_h[:, sig], F_p[:, sig]
                            elif view == "embsig":
                                Xh, Xp = np.hstack([PV, F_h[:, sig]]), np.hstack([VV, F_p[:, sig]])
                            elif view == "embsignoage":  # same, without the paper-age signal
                                Xh, Xp = np.hstack([PV, F_h[:, sig_noage]]), np.hstack([VV, F_p[:, sig_noage]])
                            elif view == "featemb":
                                Xh = np.hstack([F_h, pca.transform(PV)])
                                Xp = np.hstack([F_p, pca.transform(VV)])
                            else:
                                raise ValueError(f"unknown view in {spec!r}")
                            score = _fit_predict(model, Xh, yo, Xp, state)
                        timing[spec] += time.perf_counter() - t0
                        for pid, lab, s in zip(pool_ids, pool_y, score):
                            out.write(f"{u},{day},{pid},{lab},{spec},{float(s):.10g}\n")
                hist_ids += pool_ids
                hist_y += pool_y
                hist_days += [day] * len(pool_ids)
            out.flush()
            print(f"user {u_i + 1}/{len(users)} done; seconds so far "
                  + ", ".join(f"{s}={t:.0f}" for s, t in timing.items()), flush=True)
    print(f"Wrote {output}", flush=True)
