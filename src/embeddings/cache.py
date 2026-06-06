"""Cache de embeddings de query compartilhado entre retrievers.

No benchmark de retrieval, as mesmas 50 perguntas são embeddadas dezenas de
vezes (uma por store). Só existem 2 modelos de embedding em uso (`large` e
`small`), então só há 100 embeddings de query *únicos* no run inteiro.

Esta classe é um dicionário thread-safe com chave `(model_name, query)` que:

- intercepta `embedder.embed_query()` via `get_or_embed(embedder, query)`
- opcionalmente persiste em disco com `pickle`, pra reaproveitar entre runs

Mantém estatísticas (hits, misses) pra você medir o ganho.
"""

from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Any


class QueryEmbeddingCache:
    """Cache `(model_name, query) -> vetor` reaproveitável entre retrievers."""

    def __init__(self, persist_path: str | Path | None = None):
        self._cache: dict[tuple[str, str], list[float]] = {}
        self._persist_path: Path | None = (
            Path(persist_path) if persist_path else None
        )
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        if self._persist_path and self._persist_path.exists():
            self.load()

    def get_or_embed(self, embedder: Any, query: str) -> list[float]:
        """Devolve o embedding cacheado; computa via embedder se faltar."""
        model_name = getattr(embedder, "model_name", "unknown")
        key = (str(model_name), str(query))
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._hits += 1
                return list(cached)

        vector = embedder.embed_query(query)

        with self._lock:
            self._cache[key] = list(vector)
            self._misses += 1
        return list(vector)

    @property
    def stats(self) -> dict[str, int]:
        """Hits, misses e tamanho atual — útil pra confirmar o ganho."""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: tuple[str, str]) -> bool:
        with self._lock:
            return key in self._cache

    def save(self) -> Path:
        """Persiste o cache em disco via pickle."""
        if self._persist_path is None:
            raise RuntimeError(
                "QueryEmbeddingCache sem persist_path configurado."
            )
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            snapshot = dict(self._cache)
        with self._persist_path.open("wb") as handle:
            pickle.dump(snapshot, handle)
        return self._persist_path

    def load(self) -> None:
        """Recarrega o cache do disco (se houver `persist_path`)."""
        if self._persist_path is None or not self._persist_path.exists():
            return
        with self._persist_path.open("rb") as handle:
            snapshot = pickle.load(handle)
        if not isinstance(snapshot, dict):
            raise RuntimeError(
                f"Cache em {self._persist_path} não é um dict serializado."
            )
        with self._lock:
            self._cache.update(snapshot)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


__all__ = ["QueryEmbeddingCache"]
