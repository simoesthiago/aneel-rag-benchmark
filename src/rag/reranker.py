"""Rerankers que refinam o top-k devolvido por um Retriever.

A interface comum é `.rerank(query, docs, top_k) -> list[dict]`, recebendo
chunks com pelo menos `texto` e devolvendo os mesmos chunks reordenados,
com `score` substituído pela nota do reranker e `rank` recalculado.

Apenas `CohereReranker` está implementado por ora. A separação em módulo
permite plugar outros (BGE, voyage, etc) sem mudar `Retriever`.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx

from src.config.settings import COHERE_RERANK_MODEL, get_cohere_api_key

# Trial keys do Cohere têm rate limit de 10 req/min. Production keys
# têm limites muito maiores. Estes defaults respeitam o trial:
# até 5 retries, espera dobrando a partir de 6s (cabe no limite 10/min).
DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_BACKOFF_SECONDS = 6.0


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
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff_seconds: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
    ):
        self.model = model
        self._api_key = api_key
        self._client = client
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds

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
        response = self._call_with_retry(
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

    def _call_with_retry(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ):
        """Chama Cohere com retry exponencial em 429 e timeouts de rede.

        Dois motivos para o retry:
        - trial keys têm rate limit de 10 req/min → 429 (`TooManyRequestsError`);
        - num benchmark de ~768 chamadas, um único timeout de rede transiente
          (`httpx.TransportError`, ex.: `ReadTimeout`) não pode derrubar o run
          inteiro. Antes, só o 429 era tratado e um ReadTimeout abortava tudo.

        Production keys raramente disparam — o overhead é trivial nesses casos.
        """
        try:
            from cohere.errors import TooManyRequestsError
        except ImportError:  # versões antigas do SDK
            TooManyRequestsError = Exception  # type: ignore[assignment]

        # `httpx.TransportError` é a base de TimeoutException/NetworkError, então
        # cobre ReadTimeout, ConnectError etc. com uma só cláusula.
        retryable = (TooManyRequestsError, httpx.TransportError)

        client = self._load_client()
        backoff = self.initial_backoff_seconds
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return client.rerank(
                    model=self.model,
                    query=query,
                    documents=documents,
                    top_n=top_n,
                )
            except retryable as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2
        # Não alcançável — for-else implícito; mas mypy fica feliz
        raise last_exc if last_exc else RuntimeError("rerank falhou")


__all__ = ["CohereReranker", "Reranker"]
