"""Rerankers que refinam o top-k devolvido por um Retriever.

A interface comum é `.rerank(query, docs, top_k) -> list[dict]`, recebendo
chunks com pelo menos `texto` e devolvendo os mesmos chunks reordenados,
com `score` substituído pela nota do reranker e `rank` recalculado.

Apenas `CohereReranker` está implementado por ora. A separação em módulo
permite plugar outros (BGE, voyage, etc) sem mudar `Retriever`.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.config.settings import COHERE_RERANK_MODEL, get_cohere_api_key


class Reranker(Protocol):
    """Contrato mínimo: recebe candidatos e devolve top-k reordenado."""

    def rerank(
        self, query: str, docs: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]: ...


class CohereReranker:
    """Reranker via API da Cohere (rerank-multilingual-v3.0 por padrão)."""

    def __init__(
        self,
        *,
        model: str = COHERE_RERANK_MODEL,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        self.model = model
        self._api_key = api_key
        self._client = client

    def _load_client(self):
        if self._client is None:
            try:
                import cohere
            except ImportError as exc:
                raise RuntimeError(
                    "cohere é necessário para o CohereReranker. "
                    "Instale com `pip install cohere`."
                ) from exc
            api_key = self._api_key or get_cohere_api_key()
            self._client = cohere.Client(api_key=api_key)
        return self._client

    def rerank(
        self,
        query: str,
        docs: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not docs:
            return []
        textos = [str(doc.get("texto") or "") for doc in docs]
        response = self._load_client().rerank(
            model=self.model,
            query=query,
            documents=textos,
            top_n=min(top_k, len(textos)),
        )
        ordenado: list[dict[str, Any]] = []
        for rank, result in enumerate(response.results, start=1):
            original = dict(docs[result.index])
            original["score"] = float(result.relevance_score)
            original["rank"] = rank
            ordenado.append(original)
        return ordenado


__all__ = ["CohereReranker", "Reranker"]
