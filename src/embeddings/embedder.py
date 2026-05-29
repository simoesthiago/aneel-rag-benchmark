"""Providers de embeddings com imports pesados carregados sob demanda."""

from __future__ import annotations

import hashlib
import math
import os
from typing import Iterable

from src.config.settings import get_llm_api_key

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


class HashEmbeddingProvider:
    """Embedding deterministico leve para testes offline."""

    def __init__(self, dimension: int = 64):
        self.dimension = dimension

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbedder:
    """Wrapper lazy para Sentence Transformers, default BGE-M3."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers e necessario para embeddings BGE-M3. "
                    "Instale as dependencias de producao com requirements.txt."
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        model = self._load_model()
        return model.encode(list(texts), normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class OpenAIEmbedder:
    """Embedding opcional via API, usado somente quando configurado."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self._client = None

    def _load_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai e necessario para embeddings via API."
                ) from exc
            self._client = OpenAI(api_key=get_llm_api_key())
        return self._client

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        client = self._load_client()
        response = client.embeddings.create(model=self.model_name, input=list(texts))
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embedder(provider: str | None = None):
    """Factory simples para escolher embeddings por ambiente."""
    provider = (provider or os.environ.get("EMBEDDING_PROVIDER") or "bge-m3").lower()
    if provider in {"hash", "test"}:
        return HashEmbeddingProvider()
    if provider in {"openai", "api"}:
        return OpenAIEmbedder()
    return SentenceTransformerEmbedder(DEFAULT_EMBEDDING_MODEL)
