"""Retriever genérico sobre as vector stores publicadas na Camada 2.3.

Esta classe é o ponto de entrada da Camada 3 (Retrieval). Ela recebe a
identificação de uma das vector stores publicadas no HuggingFace Hub
(`provider`, `model`, `chunk_strategy`, `metodo_extracao`) e expõe um único
método `.retrieve(query, top_k)` que devolve os chunks ranqueados.

Toda a infra de download/cache/carregamento vem de `src.vectorstore.hub`.
O retriever só costura: vector store + embedder coerente com o manifest.

Modos suportados em `retrieve()`:

- `mode="flat"` (default): devolve o próprio chunk filho recuperado.
- `mode="hierarchical"`: válido apenas quando `chunk_strategy` é
  `hierarchical-child`. Faz busca densa nos filhos e substitui o resultado
  pelo chunk pai correspondente. Dedupe por pai mantendo o melhor score.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd

from src.embeddings.cache import QueryEmbeddingCache
from src.embeddings.embedder import OpenAIEmbeddingProvider
from src.vectorstore.faiss_store import FAISSVectorStore
from src.vectorstore.hub import carregar_vectorstore

RetrieverMode = Literal["flat", "hierarchical"]
HIERARCHICAL_CHILD_STRATEGY = "hierarchical-child"
DEFAULT_CANDIDATE_MULTIPLIER = 5
DEFAULT_MIN_CANDIDATES = 50


class Retriever:
    """Carrega uma vector store publicada e responde queries densas.

    A classe é stateful por design: o construtor paga o custo de I/O uma vez
    (download do Hub, leitura do índice, inicialização do embedder) e cada
    `.retrieve()` reaproveita esse estado. Para um benchmark com 50 perguntas
    × 12 stores, isso reduz I/O em ~50× por store.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        chunk_strategy: str,
        metodo_extracao: str,
        mode: RetrieverMode = "flat",
        repo_id: str | None = None,
        bundle: dict[str, Any] | None = None,
        embedder: Any | None = None,
        query_cache: QueryEmbeddingCache | None = None,
        reranker: Any | None = None,
        candidates_k: int | None = None,
        exclude_situacoes: frozenset[str] | None = None,
    ):
        self.provider = provider
        self.model = model
        self.chunk_strategy = chunk_strategy
        self.metodo_extracao = metodo_extracao
        self.mode: RetrieverMode = mode
        self.query_cache = query_cache
        self.reranker = reranker
        self.candidates_k = candidates_k
        # Situações de documento a descartar pós-retrieval (ex.: "revogada").
        # Normalizado para lower; o metadata herda `situacao` do documento.
        self.exclude_situacoes: frozenset[str] = frozenset(
            s.strip().lower() for s in (exclude_situacoes or frozenset())
        )

        if bundle is None:
            bundle = carregar_vectorstore(
                provider=provider,
                model=model,
                chunk_strategy=chunk_strategy,
                metodo_extracao=metodo_extracao,
                repo_id=repo_id,
            )

        self.index: FAISSVectorStore = bundle["index"]
        self.metadata: pd.DataFrame = bundle["metadata"]
        self.parents: pd.DataFrame | None = bundle["parents"]
        self.manifest: dict[str, Any] = bundle["manifest"]
        self.dir: Path | None = bundle.get("dir")

        if embedder is None:
            embedder = OpenAIEmbeddingProvider(
                model_name=self.manifest["model"]
            )
        self.embedder = embedder

        self._validar_compatibilidade_embedder()
        self._parents_by_id: dict[str, dict[str, Any]] = {}
        self._configurar_modo_hierarchical()

    def _validar_compatibilidade_embedder(self) -> None:
        """Falha cedo se o embedder não bater com o manifest da store."""
        manifest_model = self.manifest.get("model")
        embedder_model = getattr(self.embedder, "model_name", None)
        if embedder_model != manifest_model:
            raise ValueError(
                "Embedder incompatível com a vector store: "
                f"manifest.model={manifest_model!r}, "
                f"embedder.model_name={embedder_model!r}. "
                "Use o mesmo modelo que construiu a store."
            )

        manifest_dim = int(self.manifest["dimension"])
        embedder_dim = getattr(self.embedder, "dimension", None)
        if embedder_dim is not None and int(embedder_dim) != manifest_dim:
            raise ValueError(
                f"Dimensão divergente: manifest={manifest_dim}, "
                f"embedder={embedder_dim}."
            )

    def _configurar_modo_hierarchical(self) -> None:
        """Valida pré-requisitos e indexa parents do modo hierarchical."""
        if self.mode == "flat":
            return
        if self.mode != "hierarchical":
            raise ValueError(
                f"mode inválido: {self.mode!r}. Use 'flat' ou 'hierarchical'."
            )
        if self.chunk_strategy != HIERARCHICAL_CHILD_STRATEGY:
            raise ValueError(
                "mode='hierarchical' exige "
                "chunk_strategy='hierarchical-child'. "
                f"Store atual usa chunk_strategy={self.chunk_strategy!r}."
            )
        if self.parents is None or self.parents.empty:
            raise ValueError(
                "Store hierarchical-child sem parents.parquet carregado. "
                "Não é possível substituir filhos por pais."
            )
        self._parents_by_id = {
            str(row["chunk_id"]): row.to_dict()
            for _, row in self.parents.iterrows()
        }

    def retrieve(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Embedda a query e devolve os top-k chunks com score e rank.

        Em `mode='hierarchical'` busca `candidates_k` (ou top_k) filhos,
        substitui cada um pelo seu pai, dedupa mantendo o melhor score por pai,
        e re-ranqueia.

        Quando `self.reranker` está setado, busca primeiro `candidates_k`
        candidatos densos, aplica rerank, devolve os top_k finais.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query precisa ser uma string não-vazia.")

        busca_k = self._candidatos_a_buscar(top_k)

        if self.query_cache is not None:
            query_vector = self.query_cache.get_or_embed(self.embedder, query)
        else:
            query_vector = self.embedder.embed_query(query)
        scores, indices = self.index.search(query_vector, top_k=busca_k)

        candidatos: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            idx_int = int(idx)
            if idx_int < 0:
                continue
            row = self.metadata.iloc[idx_int].to_dict()
            row["score"] = float(score)
            candidatos.append(row)

        if self.exclude_situacoes:
            candidatos = [
                row
                for row in candidatos
                if str(row.get("situacao") or "").strip().lower()
                not in self.exclude_situacoes
            ]

        if self.mode == "hierarchical":
            candidatos = self._substituir_por_pais(candidatos)

        if self.reranker is not None:
            candidatos = self.reranker.rerank(query, candidatos, top_k=top_k)
            for rank, item in enumerate(candidatos, start=1):
                item["rank"] = rank
            return candidatos

        return self._rankear(candidatos, top_k)

    def _candidatos_a_buscar(self, top_k: int) -> int:
        """Quantos candidatos pegar no FAISS antes de rerank/hierarchical."""
        if self.candidates_k is not None:
            return max(self.candidates_k, top_k)
        if (
            self.reranker is not None
            or self.mode == "hierarchical"
            or self.exclude_situacoes
        ):
            # 50 candidatos é um default comum em rerankers como Cohere.
            # No hierarchical, esse piso compensa a deduplicação por pai.
            # Com filtro de situação, o piso compensa os chunks descartados.
            return max(
                top_k * DEFAULT_CANDIDATE_MULTIPLIER,
                DEFAULT_MIN_CANDIDATES,
            )
        return top_k

    def _substituir_por_pais(
        self, children: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Troca cada filho pelo pai; dedupa com melhor score."""
        melhor_por_pai: dict[str, dict[str, Any]] = {}
        for child in children:
            parent_id = child.get("parent_chunk_id")
            if not parent_id or pd.isna(parent_id):
                continue
            parent_id = str(parent_id)
            parent_row = self._parents_by_id.get(parent_id)
            if parent_row is None:
                continue
            candidato = dict(parent_row)
            candidato["score"] = float(child["score"])
            anterior = melhor_por_pai.get(parent_id)
            if anterior is None or candidato["score"] > anterior["score"]:
                melhor_por_pai[parent_id] = candidato
        return list(melhor_por_pai.values())

    @staticmethod
    def _rankear(
        items: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Ordena por score decrescente, atribui rank, e corta em top_k."""
        ordenado = sorted(items, key=lambda item: item["score"], reverse=True)
        ordenado = ordenado[:top_k]
        for rank, item in enumerate(ordenado, start=1):
            item["rank"] = rank
        return ordenado

    @property
    def store_id(self) -> str:
        """Identificação humana da store carregada."""
        return (
            f"provider={self.provider}/model={self.model}/"
            f"chunk_strategy={self.chunk_strategy}/"
            f"metodo_extracao={self.metodo_extracao}"
        )

    def __repr__(self) -> str:
        return (
            f"Retriever({self.store_id}, mode={self.mode}, "
            f"ntotal={self.index.ntotal})"
        )
