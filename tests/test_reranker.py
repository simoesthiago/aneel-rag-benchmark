"""Testes do CohereReranker e da integração com Retriever."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from src.rag.reranker import CohereReranker
from src.rag.retriever import Retriever


class _FakeCohereClient:
    """Reordena documentos simulando a estrutura da Cohere."""

    def __init__(self):
        self.calls = 0

    def rerank(self, *, model, query, documents, top_n):
        self.calls += 1
        # Inverte a ordem original — fácil de verificar no teste.
        invertido = list(range(len(documents)))[::-1]
        results = [
            SimpleNamespace(index=idx, relevance_score=1.0 - (rank * 0.1))
            for rank, idx in enumerate(invertido[:top_n])
        ]
        return SimpleNamespace(results=results)


def _chunk_row(chunk_id: str, texto: str) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": chunk_id.split("::")[0],
        "parent_chunk_id": None,
        "chunk_strategy": "article-aware",
        "chunk_level": "child",
        "chunk_index": 0,
        "metodo_extracao": "markdown",
        "extrator": "test",
        "texto": texto,
        "secao": None,
        "artigo": None,
        "paragrafo": None,
        "inciso": None,
        "alinea": None,
        "citation_label": chunk_id,
        "tipo": "ato_normativo",
        "subtipo": "ren",
        "numero": None,
        "ano": None,
        "titulo": None,
        "assunto": None,
        "situacao": "vigente",
        "fonte": None,
        "formato_original": None,
        "url_original": None,
        "url_consolidado": None,
        "qualidade_extracao": None,
    }


class _FakeEmbedder:
    def __init__(self, model_name: str, dimension: int):
        self.model_name = model_name
        self.dimension = dimension

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


class _FakeIndex:
    """Índice mínimo para integração Retriever + reranker sem FAISS local."""

    def __init__(self, vectors: list[list[float]]):
        self.vectors = np.array(vectors, dtype="float32")
        self.ntotal = len(vectors)

    def search(self, query_vector, top_k: int = 10):
        query = np.array(query_vector, dtype="float32")
        scores = self.vectors @ query
        order = np.argsort(-scores)[:top_k]
        return scores[order].reshape(1, -1), order.reshape(1, -1)


def test_cohere_reranker_reordena_via_cliente_e_devolve_top_k():
    docs = [
        {"chunk_id": "a", "texto": "primeiro"},
        {"chunk_id": "b", "texto": "segundo"},
        {"chunk_id": "c", "texto": "terceiro"},
    ]
    reranker = CohereReranker(client=_FakeCohereClient())
    ordenado = reranker.rerank("query", docs, top_k=2)

    assert [item["chunk_id"] for item in ordenado] == ["c", "b"]
    assert ordenado[0]["score"] > ordenado[1]["score"]
    assert ordenado[0]["rank"] == 1
    assert ordenado[1]["rank"] == 2


def test_cohere_reranker_lista_vazia_devolve_vazio():
    reranker = CohereReranker(client=_FakeCohereClient())
    assert reranker.rerank("q", [], top_k=5) == []


def test_retriever_com_reranker_busca_mais_candidatos_e_reordena():
    chunks = [_chunk_row(f"doc::{i}", f"texto {i}") for i in range(5)]
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.9, 0.1, 0.0, 0.0],
        [0.8, 0.2, 0.0, 0.0],
        [0.7, 0.3, 0.0, 0.0],
        [0.6, 0.4, 0.0, 0.0],
    ]
    bundle = {
        "index": _FakeIndex(vectors),
        "metadata": pd.DataFrame(chunks),
        "parents": None,
        "manifest": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimension": 4,
            "chunk_strategy": "article-aware",
            "metodo_extracao": "markdown",
            "count": 5,
        },
        "dir": None,
    }
    cohere_client = _FakeCohereClient()
    reranker = CohereReranker(client=cohere_client)
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        bundle=bundle,
        embedder=_FakeEmbedder("text-embedding-3-small", 4),
        reranker=reranker,
        candidates_k=5,
    )

    resultados = retriever.retrieve("q", top_k=3)

    assert cohere_client.calls == 1
    assert len(resultados) == 3
    # Reranker inverte a ordem dos candidatos densos (que estão por score
    # decrescente: doc::0, doc::1, doc::2, doc::3, doc::4) → top-3 pós-rerank
    # deve ser [doc::4, doc::3, doc::2].
    assert [r["chunk_id"] for r in resultados] == [
        "doc::4",
        "doc::3",
        "doc::2",
    ]
