"""Add extra label-free embedding "views" to an existing feature artifact.

Each view stores, per topic: unit-normalized candidate vectors ``vec_<view>``,
the normalized query vector ``qvec_<view>``, and a raw query-document score
``dense_<view>``. Relevance grades are copied through untouched and never read.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np

VIEWS = {
    "bge": "BAAI/bge-base-en-v1.5",
    "medcpt": "ncbi/MedCPT-Query-Encoder + ncbi/MedCPT-Article-Encoder",
}
BGE_QUERY = "Represent this sentence for searching relevant passages: "


def _unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)


def _encode_bge(queries, docs, device):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(VIEWS["bge"], device=device)
    texts = [f"{d['title']}\n{d['text']}".strip() for d in docs]
    dv = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    qv = model.encode([BGE_QUERY + q for q in queries], normalize_embeddings=True)
    return np.asarray(dv), np.asarray(qv), None


def _encode_medcpt(queries, docs, device):
    import torch
    from transformers import AutoModel, AutoTokenizer
    out = {}
    for kind, name in (("q", "ncbi/MedCPT-Query-Encoder"), ("a", "ncbi/MedCPT-Article-Encoder")):
        out[kind] = (AutoTokenizer.from_pretrained(name), AutoModel.from_pretrained(name).to(device).eval())

    def run(kind, items, max_length):
        tok, model = out[kind]
        vectors = []
        with torch.no_grad():
            for i in range(0, len(items), 64):
                enc = tok(items[i:i + 64], truncation=True, padding=True,
                          return_tensors="pt", max_length=max_length).to(device)
                vectors.append(model(**enc).last_hidden_state[:, 0, :].float().cpu().numpy())
        return np.vstack(vectors)
    dv = run("a", [[d["title"], d["text"]] for d in docs], 512)
    qv = run("q", list(queries), 64)
    return dv, qv, (dv @ qv.T)  # raw inner product is MedCPT's intended score


def add_views(*, source: Path, output: Path, views: list[str], device: str):
    unknown = set(views) - VIEWS.keys()
    if unknown:
        raise ValueError(f"Unknown views {sorted(unknown)}; choose from {sorted(VIEWS)}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty; use a new artifact directory")
    manifest = json.loads((source / "manifest.json").read_text())
    qids = manifest["selected_topics"]
    meta = {q: json.loads((source / f"topic-{q}.json").read_text()) for q in qids}
    # Encode each unique document once across topics.
    docs, index = [], {}
    for q in qids:
        for d in meta[q]["documents"]:
            if d["id"] not in index:
                index[d["id"]] = len(docs)
                docs.append(d)
    queries = [meta[q]["query"] for q in qids]
    encoded = {}
    for view in views:
        print(f"Encoding {len(docs)} documents with {VIEWS[view]}", flush=True)
        fn = _encode_bge if view == "bge" else _encode_medcpt
        encoded[view] = fn(queries, docs, device)
    output.mkdir(parents=True)
    for t, q in enumerate(qids):
        with np.load(source / f"topic-{q}.npz", allow_pickle=False) as src:
            arrays = {k: src[k] for k in src.files}
        rows = np.array([index[d] for d in arrays["doc_ids"]])
        for view, (dv, qv, raw) in encoded.items():
            vec, qvec = _unit(dv[rows]), _unit(qv[t:t + 1])[0]
            arrays[f"vec_{view}"] = vec.astype(np.float32)
            arrays[f"qvec_{view}"] = qvec.astype(np.float32)
            arrays[f"dense_{view}"] = (raw[rows, t] if raw is not None else vec @ qvec).astype(np.float32)
        np.savez_compressed(output / f"topic-{q}.npz", **arrays)
        shutil.copy(source / f"topic-{q}.json", output / f"topic-{q}.json")
    manifest["views"] = ["e5"] + views
    manifest["view_models"] = {"e5": manifest.get("encoder"), **{v: VIEWS[v] for v in views}}
    manifest["derived_from"] = str(source)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {output}", flush=True)
