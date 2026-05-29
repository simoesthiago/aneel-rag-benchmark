"""Retrievers BM25, dense, hybrid e hierarquico."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


class BM25Retriever:
    """BM25 baseline com fallback puro em Python."""

    def __init__(
        self, chunks: Iterable[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75
    ):
        self.chunks = [dict(chunk) for chunk in chunks]
        self.k1 = k1
        self.b = b
        self.tokenized = [tokenize(chunk.get("texto", "")) for chunk in self.chunks]
        self.avgdl = (
            sum(len(tokens) for tokens in self.tokenized) / len(self.tokenized)
            if self.tokenized
            else 0.0
        )
        self.doc_freq = self._document_frequencies(self.tokenized)
        self.rank_bm25 = self._build_rank_bm25()

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        query_tokens = tokenize(query)
        if self.rank_bm25 is not None:
            scores = self.rank_bm25.get_scores(query_tokens)
        else:
            scores = [
                self._score(query_tokens, index) for index in range(len(self.chunks))
            ]
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return [
            dict(self.chunks[index]) | {"score": float(score), "rank": rank}
            for rank, (index, score) in enumerate(ranked[:top_k], start=1)
        ]

    def _build_rank_bm25(self):
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return None
        return BM25Okapi(self.tokenized)

    @staticmethod
    def _document_frequencies(tokenized: list[list[str]]) -> dict[str, int]:
        frequencies: dict[str, int] = defaultdict(int)
        for tokens in tokenized:
            for token in set(tokens):
                frequencies[token] += 1
        return frequencies

    def _score(self, query_tokens: list[str], doc_index: int) -> float:
        tokens = self.tokenized[doc_index]
        if not tokens:
            return 0.0
        counts = Counter(tokens)
        score = 0.0
        doc_count = len(self.tokenized)
        doc_len = len(tokens)
        for token in query_tokens:
            df = self.doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            freq = counts[token]
            denom = freq + self.k1 * (
                1 - self.b + self.b * doc_len / (self.avgdl or 1.0)
            )
            score += idf * (freq * (self.k1 + 1)) / denom
        return score


class DenseRetriever:
    """Retriever denso sobre qualquer vector store com metodo search."""

    def __init__(self, chunks: Iterable[dict[str, Any]], embedder, vector_store):
        self.chunks = [dict(chunk) for chunk in chunks]
        self.embedder = embedder
        self.vector_store = vector_store
        texts = [chunk.get("texto", "") for chunk in self.chunks]
        embeddings = self.embedder.embed_documents(texts)
        self.vector_store.add(embeddings, self.chunks)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_embedding = self.embedder.embed_query(query)
        return self.vector_store.search(query_embedding, top_k=top_k)


class ReciprocalRankFusionHybridRetriever:
    """Combina retrievers por Reciprocal Rank Fusion."""

    def __init__(self, retrievers: Iterable[Any], *, rrf_k: int = 60):
        self.retrievers = list(retrievers)
        self.rrf_k = rrf_k

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        scores: dict[str, float] = defaultdict(float)
        best: dict[str, dict[str, Any]] = {}
        for retriever in self.retrievers:
            for rank, item in enumerate(
                retriever.retrieve(query, top_k=top_k), start=1
            ):
                chunk_id = item["chunk_id"]
                scores[chunk_id] += 1 / (self.rrf_k + rank)
                best.setdefault(chunk_id, dict(item))
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [
            best[chunk_id] | {"score": score, "rank": rank}
            for rank, (chunk_id, score) in enumerate(ranked[:top_k], start=1)
        ]


class HierarchicalRetriever:
    """Busca filhos e substitui pelo contexto pai quando disponivel."""

    def __init__(self, child_retriever, chunks: Iterable[dict[str, Any]]):
        self.child_retriever = child_retriever
        self.by_id = {chunk["chunk_id"]: dict(chunk) for chunk in chunks}

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        children = self.child_retriever.retrieve(query, top_k=top_k)
        results = []
        seen = set()
        for child in children:
            parent_id = child.get("parent_chunk_id")
            item = dict(self.by_id.get(parent_id, child)) if parent_id else dict(child)
            if item["chunk_id"] in seen:
                continue
            seen.add(item["chunk_id"])
            item["score"] = child.get("score", 0.0)
            item["rank"] = len(results) + 1
            results.append(item)
            if len(results) >= top_k:
                break
        return results
