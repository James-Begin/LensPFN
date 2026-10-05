"""Lens Feed — a personal arXiv paper feed that learns from your 👍/👎 with TabPFN-3.5.

Run:  uv run streamlit run src/lens/feed/app.py
Data stays local (``.lens-feed/``). arXiv metadata via OAI-PMH (CC0), rate-limited.
"""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import time

import numpy as np
import streamlit as st

import gzip

from lens.feed.embed import Embedder
from lens.feed.rank import FeedRanker, Profile, explain
from lens.feed.sources import TOP_LEVEL_SETS, fetch_paper, harvest, recent_window
from lens.feed.store import Store, rate, unrate

ROOT = Path(os.environ.get("LENS_FEED_HOME", ".lens-feed"))
CACHE = Path(".cache")
DEMO = Path(__file__).parent / "demo"
ENGINES = {"TabPFN-3.5-Fast": "tabpfn-fast", "TabPFN-3.5": "tabpfn",
           "Similarity baseline (Rocchio)": "similarity"}

st.set_page_config(page_title="Lens Feed", page_icon="🔭", layout="wide")


def device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


@st.cache_resource
def embedder():
    return Embedder(CACHE / "feed", device=device())


@st.cache_resource
def ranker(engine: str):
    return FeedRanker(engine=engine, device=device(), shortlist=300)


store = Store(ROOT)
profile = store.load_profile()
hidden = store.hidden()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🔭 Lens Feed")
    st.caption("New arXiv papers, ranked for you. Learns from every 👍/👎 — no training.")
    with st.expander("✨ Try the demo (offline)", expanded=not store.profile_path.exists()):
        persona = json.loads((DEMO / "persona-prior-labs.json").read_text())
        st.caption(persona["description"])
        if st.button(f"Load: {persona['name']}", use_container_width=True):
            with gzip.open(DEMO / "pool-2026-09-25-2026-10-02.json.gz", "rt") as f:
                (ROOT / "pool-demo-2026-09-25-2026-10-02.json").write_text(f.read())
            store.save_profile(Profile(likes=persona["likes"], dislikes=persona["dislikes"],
                                       interests=persona["interests"]), set(persona["hidden"]))
            st.rerun()
    interests = st.text_area("Your interests (optional)", profile.interests,
                             placeholder="e.g. tabular foundation models, retrieval, recommender systems")
    if interests != profile.interests:
        profile.interests = interests
        store.save_profile(profile, hidden)
    st.subheader("Fetch papers")
    top_set = st.selectbox("arXiv archive", sorted(TOP_LEVEL_SETS), index=sorted(TOP_LEVEL_SETS).index("cs"))
    days = st.slider("Days back", 1, 14, 7)
    if st.button("Fetch new papers from arXiv", use_container_width=True):
        start, end = recent_window(days)
        status = st.status(f"Harvesting {top_set} {start} → {end} (≤1 request / 3.5 s)…")
        papers = harvest(top_set, start, end, CACHE / "arxiv",
                         progress=lambda page, n: status.write(f"page {page}: {n} new papers"))
        store.pool_path(top_set, start, end).write_text(json.dumps(papers))
        status.update(label=f"Fetched {len(papers)} new papers", state="complete")
    st.subheader("Seed with papers you like")
    seed = st.text_input("arXiv IDs or URLs (comma-separated)", placeholder="2207.01848, 2511.08667")
    if st.button("Add as likes", use_container_width=True) and seed.strip():
        for raw in [s for s in seed.split(",") if s.strip()]:
            try:
                profile = rate(profile, fetch_paper(raw, CACHE / "arxiv"), liked=True)
            except Exception as exc:  # show and continue
                st.warning(f"{raw.strip()}: {exc}")
        store.save_profile(profile, hidden)
    st.subheader("Ranking")
    engine_label = st.radio("Engine", list(ENGINES), index=0)
    threshold = st.slider("Notify me when match ≥", 0.5, 0.99, 0.8, 0.01)
    compare = st.checkbox("Show similarity-baseline rank for comparison")

pool, pool_name = store.latest_pool()
if not pool:
    st.info("Fetch a batch of new papers from the sidebar to start (one week of cs ≈ 10k papers).")
    st.stop()

cats = sorted({p["primary"] for p in pool})
liked_cats = sorted({p["primary"] for p in profile.likes if p["primary"] in cats})
chosen = st.multiselect("Categories", cats, default=liked_cats or [c for c in ("cs.LG", "cs.IR") if c in cats])
view = [p for p in pool if not chosen or p["primary"] in chosen or set(p["categories"]) & set(chosen)]

emb = embedder()
with st.spinner(f"Embedding {len(view)} papers (cached after first run)…"):
    V = emb.papers(view)
    PV = emb.papers(profile.labeled) if profile.labeled else np.zeros((0, V.shape[1]), np.float32)
q = emb.query(profile.interests) if profile.interests.strip() else None
exclude = hidden | {p["id"] for p in profile.labeled}

t0 = time.perf_counter()
try:
    result = ranker(ENGINES[engine_label]).rank(view, V, profile, PV, q, exclude=exclude)
except Exception as exc:  # most often: TabPFN license not accepted / no TABPFN_TOKEN
    st.error("TabPFN-3.5 could not run, so Lens is showing similarity ranking instead. "
             "On first use you must accept the TabPFN license and authenticate: see "
             "https://docs.priorlabs.ai/quickstart (headless: set the TABPFN_TOKEN environment "
             f"variable). Details: {type(exc).__name__}: {str(exc)[:300]}")
    result = ranker("similarity").rank(view, V, profile, PV, q, exclude=exclude)
elapsed = time.perf_counter() - t0
baseline = None
if compare and result.engine != "similarity":
    baseline = ranker("similarity").rank(view, V, profile, PV, q, exclude=exclude)
    base_rank = {int(i): r + 1 for r, i in enumerate(np.argsort(-baseline.scores))}

order = [int(i) for i in np.argsort(-result.scores) if np.isfinite(result.scores[i])]
confident = [i for i in order if not np.isnan(result.match[i]) and result.match[i] >= threshold]

c1, c2, c3, c4 = st.columns(4)
c1.metric("New papers", f"{len(pool):,}", pool_name.removeprefix("pool-"))
c2.metric("In your categories", f"{len(view):,}")
c3.metric("Worth reading (≥ threshold)", len(confident) if result.engine != "similarity" else "—")
c4.metric("Your ratings", f"{len(profile.likes)} 👍 / {len(profile.dislikes)} 👎", f"{elapsed:.1f}s update")
rk = ranker(ENGINES[engine_label])
need = rk.ready(profile)
if ENGINES[engine_label] != "similarity" and need:
    st.info(f"Lens is learning your taste: **{need} more ratings** (include some 👎) and TabPFN-3.5 "
            "takes over, ranking by match score and filling *Worth reading*. Below ~30 ratings its "
            "probabilities are no better than your own like rate in our benchmark, so we rank by "
            "similarity and show no scores yet.")
    st.progress(min(1.0, len(profile.labeled) / rk.match_after))


def card(i: int, rank: int):
    p = view[i]
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"**{rank}. [{p['title']}]({p['url']})**")
            authors = ", ".join(p["authors"][:6]) + (" et al." if len(p["authors"]) > 6 else "")
            st.caption(f"{authors} · {' '.join(p['categories'][:4])} · submitted {p['created']}")
            why = explain(p, V[i], profile, PV) if len(PV) else {}
            bits = []
            if "closest_like" in why:
                bits.append(f"similar to *{why['closest_like'][0][:70]}* ({why['closest_like'][1]:.2f})")
            if "shared_authors" in why:
                bits.append("shared authors: " + ", ".join(why["shared_authors"]))
            if bits:
                st.caption("Why: " + " · ".join(bits))
            with st.expander("Abstract"):
                st.write(p["abstract"])
        with right:
            m = result.match[i]
            if not np.isnan(m):
                st.metric("match", ">99%" if m >= 0.995 else f"{m:.0%}")
            if baseline is not None:
                st.caption(f"baseline rank #{base_rank[i]}")
            b1, b2, b3 = st.columns(3)
            if b1.button("👍", key=f"up{p['id']}"):
                store.save_profile(rate(profile, p, True), hidden)
                st.rerun()
            if b2.button("👎", key=f"dn{p['id']}"):
                store.save_profile(rate(profile, p, False), hidden)
                st.rerun()
            if b3.button("✕", key=f"hd{p['id']}", help="Hide without rating"):
                store.save_profile(profile, hidden | {p["id"]})
                st.rerun()


feed, library = st.tabs(["For you", "Your library"])
with feed:
    shown = confident[:10] if confident else []
    if shown:
        st.subheader(f"Worth reading — match ≥ {threshold:.0%}")
        for r, i in enumerate(shown, 1):
            card(i, r)
    st.subheader("More for you" if shown else "Ranked for you")
    rest = [i for i in order if i not in set(shown)][:20]
    for r, i in enumerate(rest, len(shown) + 1):
        card(i, r)
with library:
    for label, items in (("👍 Liked", profile.likes), ("👎 Not for me", profile.dislikes)):
        st.subheader(f"{label} ({len(items)})")
        for p in items:
            a, b = st.columns([6, 1])
            a.markdown(f"[{p['title']}]({p['url']}) · {p['primary']} · rated {p.get('rated_at', '?')}")
            if b.button("remove", key=f"rm{p['id']}"):
                store.save_profile(unrate(profile, p["id"]), hidden)
                st.rerun()
st.caption("Metadata from arXiv (CC0) via OAI-PMH. Links go to arXiv abstract pages. "
           "TabPFN-3.5 weights: non-commercial license. Match scores are model estimates.")
