"""Vector stores usados pelas estrategias densas."""

from __future__ import annotations

import math
from typing import Any


class InMemoryVectorStore:
    """Vector store leve para testes e fallback local."""

    def __init__(self):
        self.embeddings: list[list[float]] = []
        self.metadata: list[dict[str, Any]] = []

    def add(
        self, embeddings: list[list[float]], metadata: list[dict[str, Any]]
    ) -> None:
        if len(embeddings) != len(metadata):
            raise ValueError("embeddings e metadata precisam ter o mesmo tamanho")
        self.embeddings.extend(embeddings)
        self.metadata.extend(metadata)

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        scored = []
        for embedding, meta in zip(self.embeddings, self.metadata):
            scored.append((cosine_similarity(query_embedding, embedding), meta))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            dict(meta) | {"score": score, "rank": index + 1}
            for index, (score, meta) in enumerate(scored[:top_k])
        ]


class FaissVectorStore:
    """FAISS com import lazy para nao quebrar desenvolvimento local."""

    def __init__(self, dimension: int):
        self.dimension = dimension
        self._faiss = None
        self._index = None
        self.metadata: list[dict[str, Any]] = []

    def _load_faiss(self):
        if self._faiss is None:
            try:
                import faiss
            except ImportError as exc:
                raise RuntimeError(
                    "faiss-cpu e necessario para usar FaissVectorStore. "
                    "Instale as dependencias de producao com requirements.txt."
                ) from exc
            self._faiss = faiss
        return self._faiss

    def add(
        self, embeddings: list[list[float]], metadata: list[dict[str, Any]]
    ) -> None:
        if len(embeddings) != len(metadata):
            raise ValueError("embeddings e metadata precisam ter o mesmo tamanho")
        if not embeddings:
            return
        faiss = self._load_faiss()
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "numpy e necessario para usar FaissVectorStore."
            ) from exc

        matrix = np.array(embeddings, dtype="float32")
        if matrix.shape[1] != self.dimension:
            raise ValueError("dimensao dos embeddings nao bate com o indice FAISS")
        faiss.normalize_L2(matrix)
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dimension)
        self._index.add(matrix)
        self.metadata.extend(metadata)

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        if self._index is None:
            return []
        self._load_faiss()
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "numpy e necessario para usar FaissVectorStore."
            ) from exc

        query = np.array([query_embedding], dtype="float32")
        self._faiss.normalize_L2(query)
        scores, indexes = self._index.search(query, top_k)
        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indexes[0]), start=1):
            if idx < 0:
                continue
            results.append(
                dict(self.metadata[int(idx)]) | {"score": float(score), "rank": rank}
            )
        return results


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)
