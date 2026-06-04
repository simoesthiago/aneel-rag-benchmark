"""Providers de embeddings para a Camada 2.2."""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any, Iterable

from src.config.settings import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    get_openai_api_key,
)

DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
}
MAX_OPENAI_BATCH_ITEMS = 2048
MAX_OPENAI_INPUT_TOKENS = 8192
MAX_OPENAI_BATCH_TOKENS = 300_000
TOKEN_SAFETY_MARGIN = 1


class HashEmbeddingProvider:
    """Embedding deterministico leve para testes offline."""

    provider = "hash"

    def __init__(self, dimension: int = 64):
        self.dimension = dimension
        self.model_name = "hash"

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in str(text).lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAIEmbeddingProvider:
    """Provider principal de embeddings via OpenAI API."""

    provider = "openai"

    def __init__(
        self,
        model_name: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        *,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        if model_name not in OPENAI_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Modelo de embedding OpenAI não suportado: {model_name}. "
                f"Use um de: {sorted(OPENAI_EMBEDDING_DIMENSIONS)}"
            )
        self.model_name = model_name
        self.dimension = OPENAI_EMBEDDING_DIMENSIONS[model_name]
        self._api_key = api_key
        self._client = client
        self.last_truncation_stats: dict[str, Any] = {}
        self.total_truncated_inputs = 0

    def _load_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai é necessário para embeddings via API. "
                    "Instale com `pip install -r requirements.txt`."
                ) from exc
            api_key = self._api_key or get_openai_api_key()
            self._client = OpenAI(api_key=api_key)
        return self._client

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        inputs = _validate_texts(texts)
        if len(inputs) > MAX_OPENAI_BATCH_ITEMS:
            raise ValueError(
                f"Lote com {len(inputs)} textos excede o limite de "
                f"{MAX_OPENAI_BATCH_ITEMS} itens da API de embeddings."
            )
        inputs, truncation_stats = prepare_openai_embedding_inputs(inputs)
        self.last_truncation_stats = truncation_stats
        self.total_truncated_inputs += int(truncation_stats["num_truncated"])

        response = self._load_client().embeddings.create(
            model=self.model_name,
            input=inputs,
            encoding_format="float",
        )
        data = sorted(response.data, key=lambda item: item.index)
        embeddings = [list(item.embedding) for item in data]
        _validate_dimensions(embeddings, self.dimension)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embedder(
    provider: str | None = None,
    model_name: str | None = None,
):
    """Factory para escolher provider/modelo por argumento ou ambiente."""
    provider = (provider or os.environ.get("EMBEDDING_PROVIDER") or "").lower()
    provider = provider or EMBEDDING_PROVIDER.lower()
    model_name = (
        model_name
        or os.environ.get("EMBEDDING_MODEL")
        or EMBEDDING_MODEL
    )

    if provider in {"hash", "test"}:
        return HashEmbeddingProvider()
    if provider in {"openai", "api"}:
        return OpenAIEmbeddingProvider(model_name=model_name)
    raise ValueError(
        f"EMBEDDING_PROVIDER inválido: {provider}. "
        "Use 'openai' ou 'hash'."
    )


def _validate_texts(texts: Iterable[str]) -> list[str]:
    inputs = [str(text).strip() for text in texts]
    if not inputs:
        raise ValueError("Nenhum texto informado para embedding.")
    empty_indexes = [index for index, text in enumerate(inputs) if not text]
    if empty_indexes:
        raise ValueError(
            "Textos vazios não podem ser enviados para embeddings. "
            f"Índices vazios: {empty_indexes[:10]}"
        )
    return inputs


def prepare_openai_embedding_inputs(
    texts: Iterable[str],
    *,
    max_input_tokens: int = MAX_OPENAI_INPUT_TOKENS,
    max_batch_tokens: int = MAX_OPENAI_BATCH_TOKENS,
) -> tuple[list[str], dict[str, Any]]:
    """Trunca textos para respeitar limites da API de embeddings da OpenAI.

    Mantemos essa lógica antes da chamada à API para evitar desperdiçar uma
    execução longa quando um único chunk patológico passa do limite de tokens.
    A camada de vector store preserva o texto completo no metadata; a versão
    truncada é usada somente para gerar o vetor.
    """
    inputs = _validate_texts(texts)
    per_input_limit = min(
        max_input_tokens - TOKEN_SAFETY_MARGIN,
        max_batch_tokens // len(inputs),
    )
    encoding = _load_tiktoken_encoding()

    prepared: list[str] = []
    num_truncated = 0
    max_tokens_seen = 0

    for text in inputs:
        truncated, token_count = _truncate_text_for_embedding(
            text,
            per_input_limit=per_input_limit,
            encoding=encoding,
        )
        max_tokens_seen = max(max_tokens_seen, token_count)
        if truncated != text:
            num_truncated += 1
        prepared.append(truncated)

    stats = {
        "num_inputs": len(inputs),
        "num_truncated": num_truncated,
        "max_tokens_seen": max_tokens_seen,
        "per_input_token_limit": per_input_limit,
        "max_batch_tokens": max_batch_tokens,
        "tokenizer": "tiktoken:cl100k_base" if encoding is not None else "fallback",
    }
    return prepared, stats


def _load_tiktoken_encoding() -> Any | None:
    """Carrega tiktoken quando disponível; fallback conserva testes sem a dep."""
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _truncate_text_for_embedding(
    text: str,
    *,
    per_input_limit: int,
    encoding: Any | None,
) -> tuple[str, int]:
    """Devolve `(texto_para_embedding, tokens_estimados_ou_reais)`."""
    if encoding is not None:
        tokens = encoding.encode(text)
        if len(tokens) <= per_input_limit:
            return text, len(tokens)
        return encoding.decode(tokens[:per_input_limit]), len(tokens)

    # Fallback conservador quando tiktoken ainda não está instalado. Para o
    # corpus ANEEL (português/markdown), 3 chars por token é prudente o bastante
    # para evitar estouros sem apagar metadados ou texto original.
    max_chars = per_input_limit * 3
    token_estimate = max(1, math.ceil(len(text) / 3))
    if len(text) <= max_chars:
        return text, token_estimate
    return text[:max_chars], token_estimate


def _validate_dimensions(
    embeddings: list[list[float]], expected_dimension: int
) -> None:
    invalid = [
        index
        for index, embedding in enumerate(embeddings)
        if len(embedding) != expected_dimension
    ]
    if invalid:
        raise RuntimeError(
            "Embedding retornou dimensão inesperada. "
            f"Esperado={expected_dimension}; índices inválidos={invalid[:10]}"
        )
