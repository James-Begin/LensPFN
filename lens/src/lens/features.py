"""Label-free feature construction; qrels are consulted only after selection."""
from __future__ import annotations

import json
from pathlib import Path
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from lens.data import download, load_topics


# Leading columns of X that are topic-relative (BM25/dense/base score blocks + length);
# the remainder are corpus-level PCA coordinates, which do not transfer across topics.
STATIC_COLUMNS = 10


def tokenize(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())


def score_features(score):
    """Topic-relative scales; no labels used."""
    rank = np.argsort(np.argsort(-score, kind="stable"), kind="stable")
    return np.column_stack([
        (score - score.mean()) / max(float(score.std()), 1e-8),
        rank / max(len(score) - 1, 1),
        score - score.max(),
    ])


def prepare(*, cache: Path, output: Path, topics: int, split: str, seed: int,
            pool_size: int, mode: str, device: str, dev_fraction: float = 0.2):
    if pool_size != 0 and pool_size < 2:
        raise ValueError("--pool-size must be 0 (full judged pool) or at least 2")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty; use a new artifact directory")
    queries, judgments, docs, selected, manifest = load_topics(
        download(cache), count=topics, split=split, seed=seed, dev_fraction=dev_fraction,
    )
    doc_ids = sorted(docs)
    doc_index = {doc_id: i for i, doc_id in enumerate(doc_ids)}
    texts = [f"{docs[d].get('title', '')} {docs[d].get('text', '')}".strip() for d in doc_ids]
    print(f"Building {mode} features for {len(doc_ids)} judged documents", flush=True)
    bm25 = BM25Okapi([tokenize(text) for text in texts])
    encoder = reranker = None
    if mode == "semantic":
        try:
            from sentence_transformers import CrossEncoder, SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install semantic dependencies: uv sync --extra semantic") from exc
        encoder = SentenceTransformer("intfloat/e5-small-v2", device=device)
        vectors = encoder.encode(
            [f"passage: {text}" for text in texts], batch_size=32,
            normalize_embeddings=True, show_progress_bar=True,
        )
        query_vectors = encoder.encode(
            [f"query: {queries[q]}" for q in selected], normalize_embeddings=True,
        )
        reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", device=device)
        reduced = PCA(n_components=min(16, *vectors.shape), random_state=seed).fit_transform(vectors)
    else:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=20000, min_df=1)
        tfidf = vectorizer.fit_transform(texts)
        svd = TruncatedSVD(n_components=min(32, tfidf.shape[1] - 1, len(doc_ids) - 1), random_state=seed)
        vectors = normalize(svd.fit_transform(tfidf))
        query_vectors = normalize(svd.transform(vectorizer.transform([queries[q] for q in selected])))
        reduced = vectors[:, :16]
    output.mkdir(parents=True, exist_ok=True)
    manifest.update({
        "feature_mode": mode,
        "pool_size": pool_size,
        "feature_device": device,
        "encoder": "intfloat/e5-small-v2" if encoder else "TF-IDF + SVD (engineering smoke only)",
        "reranker": "cross-encoder/ms-marco-MiniLM-L6-v2" if reranker else None,
        "projection_fit": "selected corpus documents only; label-free and transductive",
        "pool_policy": "reciprocal-rank fusion of BM25 and similarity within explicitly judged pool",
    })
    for topic_number, qid in enumerate(selected):
        eligible = sorted(judgments[qid])  # Keys only; relevance values are not read here.
        indices = np.array([doc_index[d] for d in eligible])
        bm = np.asarray(bm25.get_scores(tokenize(queries[qid])))[indices]
        dense = vectors[indices] @ query_vectors[topic_number]
        bm_rank = np.argsort(np.argsort(-bm, kind="stable"), kind="stable")
        dense_rank = np.argsort(np.argsort(-dense, kind="stable"), kind="stable")
        fusion = 1 / (60 + bm_rank + 1) + 1 / (60 + dense_rank + 1)
        chosen = np.argsort(-fusion, kind="stable")
        if pool_size:
            chosen = chosen[:pool_size]
        pool_ids = [eligible[i] for i in chosen]
        pool_indices = indices[chosen]
        bm, dense, fusion = bm[chosen], dense[chosen], fusion[chosen]
        if reranker:
            base = np.asarray(reranker.predict(
                [(queries[qid], texts[i]) for i in pool_indices], batch_size=32,
                show_progress_bar=False,
            )).reshape(-1)
        else:
            base = fusion
        features = np.column_stack([
            score_features(bm), score_features(dense), score_features(base),
            np.log1p([len(tokenize(texts[i])) for i in pool_indices]),
            reduced[pool_indices],
        ]).astype(np.float32)
        # Outcome labels enter only after candidate selection and feature construction.
        grades = np.array([judgments[qid][d] for d in pool_ids], dtype=np.int32)
        np.savez_compressed(
            output / f"topic-{qid}.npz", X=features, vectors=vectors[pool_indices],
            query_vector=query_vectors[topic_number], base=base, grades=grades,
            doc_ids=np.array(pool_ids),
        )
        (output / f"topic-{qid}.json").write_text(json.dumps({
            "query_id": qid, "query": queries[qid],
            "documents": [{"id": d, "title": docs[d].get("title", ""),
                           "text": docs[d].get("text", "")} for d in pool_ids],
        }, indent=2))
        print(f"Topic {qid}: {len(pool_ids)} candidates, {int((grades > 0).sum())} relevant, "
              f"{int((grades == 2).sum())} highly relevant", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
