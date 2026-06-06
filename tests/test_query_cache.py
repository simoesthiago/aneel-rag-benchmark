"""Testes do cache de embeddings de query."""

from __future__ import annotations

from src.embeddings.cache import QueryEmbeddingCache


class _CountingEmbedder:
    """Conta chamadas para validar que o cache de fato evita recomputação."""

    def __init__(self, model_name: str = "test-model"):
        self.model_name = model_name
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return [float(ord(ch)) for ch in text[:4]]


def test_cache_devolve_mesmo_vetor_em_chamadas_repetidas():
    cache = QueryEmbeddingCache()
    embedder = _CountingEmbedder()

    v1 = cache.get_or_embed(embedder, "consumidor")
    v2 = cache.get_or_embed(embedder, "consumidor")

    assert v1 == v2
    assert embedder.calls == 1
    assert cache.stats["hits"] == 1
    assert cache.stats["misses"] == 1


def test_cache_separa_modelos_distintos():
    cache = QueryEmbeddingCache()
    embedder_a = _CountingEmbedder("modelo-A")
    embedder_b = _CountingEmbedder("modelo-B")

    cache.get_or_embed(embedder_a, "x")
    cache.get_or_embed(embedder_b, "x")

    assert embedder_a.calls == 1
    assert embedder_b.calls == 1
    assert cache.stats["size"] == 2


def test_cache_persistencia_pra_disco_e_recarregamento(tmp_path):
    path = tmp_path / "cache.pkl"

    cache = QueryEmbeddingCache(persist_path=path)
    embedder = _CountingEmbedder()
    cache.get_or_embed(embedder, "pergunta")
    cache.save()
    assert path.exists()

    novo = QueryEmbeddingCache(persist_path=path)
    novo_embedder = _CountingEmbedder()
    novo.get_or_embed(novo_embedder, "pergunta")

    assert novo_embedder.calls == 0
    assert novo.stats["hits"] == 1
