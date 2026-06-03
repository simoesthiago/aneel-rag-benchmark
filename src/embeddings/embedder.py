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
