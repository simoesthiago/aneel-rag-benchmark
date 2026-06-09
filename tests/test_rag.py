"""Testes da Camada 3 (Retrieval).

O foco aqui é o contrato do `Retriever`: carregamento de uma vector store
publicada, compatibilidade com o manifest e formato dos resultados. Os testes
usam um bundle injetado para evitar dependência de rede (HuggingFace Hub) e
de API paga (OpenAI).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.rag.naive import NaiveRAG
from src.rag.retriever import Retriever


def _chunk_row(
    chunk_id: str,
    texto: str,
    *,
    document_id: str | None = None,
    citation_label: str | None = None,
    parent_chunk_id: str | None = None,
) -> dict:
    """Linha minimamente compatível com o schema do metadata.parquet."""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id or chunk_id.split("::")[0],
        "parent_chunk_id": parent_chunk_id,
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
        "citation_label": citation_label or chunk_id,
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
    """Embedder determinístico para testes — não chama OpenAI."""

    def __init__(
        self,
        model_name: str,
        dimension: int,
        vectors: dict[str, list[float]],
    ):
        self.model_name = model_name
        self.dimension = dimension
        self._vectors = vectors

    def embed_query(self, text: str) -> list[float]:
        if text not in self._vectors:
            raise KeyError(f"Vetor não definido para query: {text!r}")
        return self._vectors[text]


class _FakeIndex:
    """Índice vetorial mínimo para testar Retriever sem depender de FAISS."""

    def __init__(self, vectors: list[list[float]], dimension: int):
        self.dimension = dimension
        self.vectors = np.array(vectors, dtype="float32")
        self.ntotal = len(vectors)
        self.search_calls: list[int] = []

    def search(self, query_vector, top_k: int = 10):
        self.search_calls.append(top_k)
        query = np.array(query_vector, dtype="float32")
        if query.ndim == 1:
            query = query.reshape(1, -1)
        scores = self.vectors @ query[0]
        order = np.argsort(-scores)[:top_k]
        return scores[order].reshape(1, -1), order.reshape(1, -1)


def _build_index(vectors: list[list[float]], dimension: int) -> _FakeIndex:
    return _FakeIndex(vectors, dimension)


def _build_bundle(
    chunks: list[dict],
    vectors: list[list[float]],
    *,
    model: str = "text-embedding-3-small",
    dimension: int = 4,
    chunk_strategy: str = "article-aware",
    parents: pd.DataFrame | None = None,
) -> dict:
    metadata = pd.DataFrame(chunks)
    index = _build_index(vectors, dimension)
    manifest = {
        "provider": "openai",
        "model": model,
        "dimension": dimension,
        "chunk_strategy": chunk_strategy,
        "metodo_extracao": "markdown",
        "count": len(chunks),
    }
    return {
        "index": index,
        "metadata": metadata,
        "parents": parents,
        "manifest": manifest,
        "dir": None,
    }


def test_retriever_carrega_bundle_e_devolve_top_k_ordenado():
    chunks = [
        _chunk_row("doc-a::0", "primeiro chunk", citation_label="Art. 1º"),
        _chunk_row("doc-b::0", "segundo chunk", citation_label="Art. 2º"),
        _chunk_row("doc-c::0", "terceiro chunk", citation_label="Art. 3º"),
    ]
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
    bundle = _build_bundle(chunks, vectors)
    embedder = _FakeEmbedder(
        "text-embedding-3-small",
        dimension=4,
        vectors={"qual o artigo dois?": [0.0, 1.0, 0.0, 0.0]},
    )

    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        bundle=bundle,
        embedder=embedder,
    )

    resultados = retriever.retrieve("qual o artigo dois?", top_k=2)

    assert len(resultados) == 2
    assert resultados[0]["chunk_id"] == "doc-b::0"
    assert resultados[0]["rank"] == 1
    assert resultados[0]["score"] > resultados[1]["score"]
    assert resultados[0]["citation_label"] == "Art. 2º"
    assert "texto" in resultados[0]


def test_retriever_rejeita_query_vazia():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "algum texto")],
        [[1.0, 0.0, 0.0, 0.0]],
    )
    embedder = _FakeEmbedder("text-embedding-3-small", 4, {})
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        bundle=bundle,
        embedder=embedder,
    )

    with pytest.raises(ValueError, match="query"):
        retriever.retrieve("   ", top_k=5)


def test_retriever_falha_se_embedder_modelo_divergente_do_manifest():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "texto")],
        [[1.0, 0.0, 0.0, 0.0]],
        model="text-embedding-3-small",
    )
    embedder_errado = _FakeEmbedder(
        "text-embedding-3-large", dimension=4, vectors={}
    )

    with pytest.raises(ValueError, match="Embedder incompatível"):
        Retriever(
            provider="openai",
            model="text-embedding-3-small",
            chunk_strategy="article-aware",
            metodo_extracao="markdown",
            bundle=bundle,
            embedder=embedder_errado,
        )


def test_retriever_falha_se_dimensao_embedder_divergente():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "texto")],
        [[1.0, 0.0, 0.0, 0.0]],
        model="text-embedding-3-small",
        dimension=4,
    )
    embedder_errado = _FakeEmbedder(
        "text-embedding-3-small", dimension=8, vectors={}
    )

    with pytest.raises(ValueError, match="Dimensão"):
        Retriever(
            provider="openai",
            model="text-embedding-3-small",
            chunk_strategy="article-aware",
            metodo_extracao="markdown",
            bundle=bundle,
            embedder=embedder_errado,
        )


def test_retriever_usa_query_cache_quando_passado():
    """Cache compartilhado evita re-chamar o embedder pra a mesma query."""
    from src.embeddings.cache import QueryEmbeddingCache

    chunks = [_chunk_row("doc-a::0", "primeiro chunk")]
    vectors = [[1.0, 0.0, 0.0, 0.0]]
    bundle = _build_bundle(chunks, vectors)

    class _Counter(_FakeEmbedder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        def embed_query(self, text: str) -> list[float]:
            self.calls += 1
            return super().embed_query(text)

    embedder = _Counter(
        "text-embedding-3-small",
        dimension=4,
        vectors={"q": [1.0, 0.0, 0.0, 0.0]},
    )
    cache = QueryEmbeddingCache()
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        bundle=bundle,
        embedder=embedder,
        query_cache=cache,
    )

    retriever.retrieve("q", top_k=1)
    retriever.retrieve("q", top_k=1)

    assert embedder.calls == 1
    assert cache.stats["hits"] == 1


def test_retriever_store_id_descreve_a_store_carregada():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "texto")],
        [[1.0, 0.0, 0.0, 0.0]],
    )
    embedder = _FakeEmbedder("text-embedding-3-small", 4, {})
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        bundle=bundle,
        embedder=embedder,
    )

    assert retriever.store_id == (
        "provider=openai/model=text-embedding-3-small/"
        "chunk_strategy=article-aware/metodo_extracao=markdown"
    )
    assert "ntotal=1" in repr(retriever)


def test_retriever_hierarchical_substitui_filho_por_pai():
    children = [
        _chunk_row(
            "doc-a::child::0",
            "trecho do filho 1",
            citation_label="Art. 1º §1º",
            parent_chunk_id="doc-a::parent::A",
        ),
        _chunk_row(
            "doc-a::child::1",
            "trecho do filho 2",
            citation_label="Art. 1º §2º",
            parent_chunk_id="doc-a::parent::A",
        ),
        _chunk_row(
            "doc-a::child::2",
            "trecho do filho 3",
            citation_label="Art. 2º",
            parent_chunk_id="doc-a::parent::B",
        ),
    ]
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.9, 0.1, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
    parents = pd.DataFrame(
        [
            _chunk_row(
                "doc-a::parent::A",
                "texto completo do artigo 1",
                citation_label="Art. 1º",
            ),
            _chunk_row(
                "doc-a::parent::B",
                "texto completo do artigo 2",
                citation_label="Art. 2º",
            ),
        ]
    )
    bundle = _build_bundle(
        children,
        vectors,
        chunk_strategy="hierarchical-child",
        parents=parents,
    )
    embedder = _FakeEmbedder(
        "text-embedding-3-small",
        dimension=4,
        vectors={"qual o artigo um?": [1.0, 0.0, 0.0, 0.0]},
    )

    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="hierarchical-child",
        metodo_extracao="markdown",
        mode="hierarchical",
        bundle=bundle,
        embedder=embedder,
    )

    resultados = retriever.retrieve("qual o artigo um?", top_k=3)

    # 3 filhos retornados, mas só 2 pais distintos → dedup deve produzir 2.
    assert len(resultados) == 2
    ids = [r["chunk_id"] for r in resultados]
    assert ids[0] == "doc-a::parent::A"
    assert ids[1] == "doc-a::parent::B"

    # O pai A herda o MELHOR score entre seus filhos (1.0 do filho 0).
    pai_a = resultados[0]
    assert pai_a["score"] == pytest.approx(1.0)
    assert pai_a["texto"] == "texto completo do artigo 1"
    assert pai_a["rank"] == 1


def test_retriever_hierarchical_busca_mais_filhos_antes_de_deduplicar():
    children = [
        _chunk_row(
            f"doc-a::child::{idx}",
            f"filho {idx}",
            parent_chunk_id=(
                "doc-a::parent::A" if idx < 3 else "doc-a::parent::B"
            ),
        )
        for idx in range(4)
    ]
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.9, 0.0, 0.0, 0.0],
        [0.8, 0.0, 0.0, 0.0],
        [0.7, 0.0, 0.0, 0.0],
    ]
    parents = pd.DataFrame(
        [
            _chunk_row("doc-a::parent::A", "pai A"),
            _chunk_row("doc-a::parent::B", "pai B"),
        ]
    )
    bundle = _build_bundle(
        children,
        vectors,
        chunk_strategy="hierarchical-child",
        parents=parents,
    )
    embedder = _FakeEmbedder(
        "text-embedding-3-small",
        dimension=4,
        vectors={"q": [1.0, 0.0, 0.0, 0.0]},
    )
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-small",
        chunk_strategy="hierarchical-child",
        metodo_extracao="markdown",
        mode="hierarchical",
        bundle=bundle,
        embedder=embedder,
    )

    resultados = retriever.retrieve("q", top_k=2)

    assert bundle["index"].search_calls == [50]
    assert [item["chunk_id"] for item in resultados] == [
        "doc-a::parent::A",
        "doc-a::parent::B",
    ]


def test_retriever_hierarchical_rejeita_store_nao_hierarquica():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "texto")],
        [[1.0, 0.0, 0.0, 0.0]],
        chunk_strategy="article-aware",
    )
    embedder = _FakeEmbedder("text-embedding-3-small", 4, {})

    with pytest.raises(ValueError, match="hierarchical-child"):
        Retriever(
            provider="openai",
            model="text-embedding-3-small",
            chunk_strategy="article-aware",
            metodo_extracao="markdown",
            mode="hierarchical",
            bundle=bundle,
            embedder=embedder,
        )


def test_retriever_hierarchical_rejeita_store_sem_parents():
    children = [
        _chunk_row(
            "doc-a::child::0",
            "filho sem pai indexado",
            parent_chunk_id="doc-a::parent::Z",
        )
    ]
    bundle = _build_bundle(
        children,
        [[1.0, 0.0, 0.0, 0.0]],
        chunk_strategy="hierarchical-child",
        parents=None,
    )
    embedder = _FakeEmbedder("text-embedding-3-small", 4, {})

    with pytest.raises(ValueError, match="parents"):
        Retriever(
            provider="openai",
            model="text-embedding-3-small",
            chunk_strategy="hierarchical-child",
            metodo_extracao="markdown",
            mode="hierarchical",
            bundle=bundle,
            embedder=embedder,
        )


def test_retriever_modo_invalido_falha_cedo():
    bundle = _build_bundle(
        [_chunk_row("doc-a::0", "texto")],
        [[1.0, 0.0, 0.0, 0.0]],
    )
    embedder = _FakeEmbedder("text-embedding-3-small", 4, {})

    with pytest.raises(ValueError, match="mode inválido"):
        Retriever(
            provider="openai",
            model="text-embedding-3-small",
            chunk_strategy="article-aware",
            metodo_extracao="markdown",
            mode="hibrido",  # type: ignore[arg-type]
            bundle=bundle,
            embedder=embedder,
        )


def test_naive_rag_usa_contrato_retrieve_top_k():
    """NaiveRAG mantém o contrato com o retriever."""

    class FakeRetriever:
        def retrieve(self, query, top_k=5):
            return [
                {
                    "chunk_id": "doc-a::0",
                    "texto": "texto recuperado",
                    "citation_label": "Art. 1º",
                    "score": 1.0,
                    "rank": 1,
                }
            ]

    rag = NaiveRAG(FakeRetriever(), strategy="dense")
    resposta = rag.query("pergunta", top_k=5)

    # contrato mínimo: campos sempre presentes (com ou sem expander).
    assert {
        "answer",
        "citations",
        "contexts",
        "latency_ms",
        "strategy",
        "query",
        "expanded_query",
        "query_expansion_status",
        "query_expansion_error",
    }.issubset(set(resposta))
    assert resposta["strategy"] == "dense"
    assert resposta["citations"] == ["Art. 1º"]
    assert resposta["latency_ms"] >= 0
    # sem expander injetado, query_expansion_status sinaliza "disabled".
    assert resposta["query"] == "pergunta"
    assert resposta["expanded_query"] == "pergunta"
    assert resposta["query_expansion_status"] == "disabled"


def test_naive_rag_usa_query_expandida_no_retriever_e_original_no_generator():
    """Contrato Fase 2: retriever vê query expandida, generator vê original."""

    class RecordingRetriever:
        def __init__(self):
            self.received: list[str] = []

        def retrieve(self, query, top_k=5):
            self.received.append(query)
            return [
                {
                    "chunk_id": "doc-x::0",
                    "texto": "texto",
                    "citation_label": "Art. 1º",
                    "score": 1.0,
                    "rank": 1,
                }
            ]

    class RecordingGenerator:
        def __init__(self):
            self.received: list[str] = []

        def __call__(self, query, contexts):
            self.received.append(query)
            return {
                "answer": "resposta gerada",
                "citations_used": [1],
                "raw": "",
                "llm_status": "ok",
                "llm_error": None,
            }

    class FakeExpander:
        def expand(self, query):
            return {
                "expanded_query": f"{query} [expandido]",
                "added_terms": ["termo-A", "termo-B"],
                "status": "ok",
                "error": None,
            }

    retriever = RecordingRetriever()
    generator = RecordingGenerator()
    rag = NaiveRAG(
        retriever,
        strategy="dense+qe",
        generator=generator,
        query_expander=FakeExpander(),
    )

    resposta = rag.query("Qual é a finalidade do PRORET Submódulo 2.4?", top_k=3)

    assert retriever.received == ["Qual é a finalidade do PRORET Submódulo 2.4? [expandido]"]
    assert generator.received == ["Qual é a finalidade do PRORET Submódulo 2.4?"]
    assert resposta["query"] == "Qual é a finalidade do PRORET Submódulo 2.4?"
    assert resposta["expanded_query"].endswith("[expandido]")
    assert resposta["query_expansion_status"] == "ok"
    assert resposta["query_expansion_error"] is None
    assert resposta["answer"] == "resposta gerada"
