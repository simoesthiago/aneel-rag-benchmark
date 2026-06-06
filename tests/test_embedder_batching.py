"""Testes do batching + retry do OpenAIEmbeddingProvider."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.embeddings.embedder import (
    DEFAULT_EMBED_BATCH_SIZE,
    OPENAI_EMBEDDING_DIMENSIONS,
    OpenAIEmbeddingProvider,
)


class _FakeOpenAIClient:
    """Cliente fake que conta chamadas e devolve vetores determinísticos."""

    def __init__(self, dimension: int, fail_first_n: int = 0):
        self.dimension = dimension
        self.calls = 0
        self.fail_first_n = fail_first_n
        self.embeddings = self  # mimics client.embeddings.create

    def create(self, *, model: str, input: list[str], encoding_format: str):
        self.calls += 1
        if self.calls <= self.fail_first_n:

            class _RateLimitError(Exception):
                pass

            _RateLimitError.__name__ = "RateLimitError"
            raise _RateLimitError("simulated rate limit")
        data = [
            SimpleNamespace(index=i, embedding=[0.0] * self.dimension)
            for i in range(len(input))
        ]
        return SimpleNamespace(data=data)


def _provider(
    client: _FakeOpenAIClient,
    model: str = "text-embedding-3-small",
):
    return OpenAIEmbeddingProvider(model_name=model, client=client)


def test_embed_documents_quebra_em_sub_lotes():
    dim = OPENAI_EMBEDDING_DIMENSIONS["text-embedding-3-small"]
    client = _FakeOpenAIClient(dim)
    provider = _provider(client)

    textos = [f"texto {i}" for i in range(DEFAULT_EMBED_BATCH_SIZE * 2 + 3)]
    vetores = provider.embed_documents(
        textos,
        batch_size=DEFAULT_EMBED_BATCH_SIZE,
    )

    assert len(vetores) == len(textos)
    assert client.calls == 3  # ceil((512+3) / 256) = 3


def test_embed_documents_retry_em_rate_limit_eventualmente_sucede():
    dim = OPENAI_EMBEDDING_DIMENSIONS["text-embedding-3-small"]
    client = _FakeOpenAIClient(dim, fail_first_n=2)
    provider = _provider(client)

    vetores = provider.embed_documents(["x"])

    assert len(vetores) == 1
    # 2 falhas + 1 sucesso = 3 chamadas no cliente.
    assert client.calls == 3


def test_embed_documents_estoura_apos_max_tentativas():
    dim = OPENAI_EMBEDDING_DIMENSIONS["text-embedding-3-small"]
    client = _FakeOpenAIClient(dim, fail_first_n=99)
    provider = _provider(client)

    with pytest.raises(Exception, match="rate limit"):
        provider.embed_documents(["x"])
