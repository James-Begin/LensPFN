"""Incremental on-disk embedding cache (e5-small-v2, unit-normalized)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

MODEL = "intfloat/e5-small-v2"


class Embedder:
    def __init__(self, cache: Path, device: str = "cpu"):
        self.path = cache / "embeddings-e5-small-v2.npz"
        self.device = device
        self._model = None
        self.index: dict[str, int] = {}
        self.vectors = np.zeros((0, 384), dtype=np.float32)
        if self.path.exists():
            with np.load(self.path, allow_pickle=False) as data:
                self.vectors = data["vectors"]
                self.index = {str(i): k for k, i in enumerate(data["ids"])}

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL, device=self.device)
        return self._model

    def papers(self, papers: list[dict], progress=None) -> np.ndarray:
        missing = [p for p in papers if p["id"] not in self.index]
        if missing:
            texts = [f"passage: {p['title']}. {p['abstract']}" for p in missing]
            new = []
            for i in range(0, len(texts), 256):
                new.append(self.model.encode(texts[i:i + 256], batch_size=64,
                                             normalize_embeddings=True, show_progress_bar=False))
                if progress:
                    progress(min(i + 256, len(texts)), len(texts))
            start = len(self.vectors)
            self.vectors = np.vstack([self.vectors, *new]).astype(np.float32)
            for k, p in enumerate(missing):
                self.index[p["id"]] = start + k
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ids = np.array(sorted(self.index, key=self.index.get))
            np.savez(self.path, ids=ids, vectors=self.vectors)
        return self.vectors[[self.index[p["id"]] for p in papers]]

    def query(self, text: str) -> np.ndarray:
        return self.model.encode([f"query: {text}"], normalize_embeddings=True)[0]
