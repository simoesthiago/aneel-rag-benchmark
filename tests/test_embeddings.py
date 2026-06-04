import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest


def _chunks_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "chunk_id": "doc-1::markdown::fixed-size::0000",
                "texto": "primeiro texto",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "tipo": "ato_normativo",
            },
            {
                "chunk_id": "doc-2::markdown::fixed-size::0000",
                "texto": "segundo texto",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "tipo": "manual",
            },
            {
                "chunk_id": "doc-3::markdown::fixed-size::0000",
                "texto": "terceiro texto",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "tipo": "lei",
            },
        ]
    )


def test_hash_embedding_provider_retorna_dimensao_estavel():
    from src.embeddings.embedder import HashEmbeddingProvider

    provider = HashEmbeddingProvider(dimension=8)

    vector = provider.embed_query("REN 1000 consumidor")

    assert len(vector) == 8
    assert pytest.approx(sum(value * value for value in vector)) == 1.0
    assert provider.provider == "hash"
    assert provider.model_name == "hash"


def test_build_embedder_respeita_env_vars(monkeypatch):
    from src.embeddings.embedder import OpenAIEmbeddingProvider, build_embedder

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")

    provider = build_embedder()

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.model_name == "text-embedding-3-small"
    assert provider.dimension == 1536


def test_build_embedder_rejeita_provider_invalido():
    from src.embeddings.embedder import build_embedder

    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER inválido"):
        build_embedder(provider="local")


def test_openai_provider_preserva_ordem_com_client_mockado():
    from src.embeddings.embedder import OpenAIEmbeddingProvider

    class FakeEmbeddings:
        def create(self, model, input, encoding_format):
            assert model == "text-embedding-3-small"
            assert encoding_format == "float"
            data = [
                SimpleNamespace(index=1, embedding=[2.0] * 1536),
                SimpleNamespace(index=0, embedding=[1.0] * 1536),
            ]
            return SimpleNamespace(data=data)

    client = SimpleNamespace(embeddings=FakeEmbeddings())
    provider = OpenAIEmbeddingProvider(
        model_name="text-embedding-3-small", client=client
    )

    embeddings = provider.embed_documents(["a", "b"])

    assert embeddings[0][0] == 1.0
    assert embeddings[1][0] == 2.0


def test_openai_provider_trunca_texto_longo_antes_da_api():
    from src.embeddings.embedder import OpenAIEmbeddingProvider

    texto_longo = "palavra " * 20_000

    class FakeEmbeddings:
        def create(self, model, input, encoding_format):
            assert model == "text-embedding-3-small"
            assert encoding_format == "float"
            assert len(input) == 1
            assert len(input[0]) < len(texto_longo)
            return SimpleNamespace(
                data=[SimpleNamespace(index=0, embedding=[1.0] * 1536)]
            )

    client = SimpleNamespace(embeddings=FakeEmbeddings())
    provider = OpenAIEmbeddingProvider(
        model_name="text-embedding-3-small", client=client
    )

    embeddings = provider.embed_documents([texto_longo])

    assert len(embeddings[0]) == 1536
    assert provider.last_truncation_stats["num_truncated"] == 1
    assert provider.total_truncated_inputs == 1


def test_openai_provider_falha_sem_chave(monkeypatch):
    from src.embeddings.embedder import OpenAIEmbeddingProvider

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = lambda api_key: SimpleNamespace()
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    provider = OpenAIEmbeddingProvider(model_name="text-embedding-3-small")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.embed_query("consulta")


def test_openai_provider_rejeita_placeholder_de_chave(monkeypatch):
    from src.embeddings.embedder import OpenAIEmbeddingProvider

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = lambda api_key: SimpleNamespace()
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "sua_chave_aqui")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    provider = OpenAIEmbeddingProvider(model_name="text-embedding-3-small")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.embed_query("consulta")


def test_gerar_embeddings_chunks_preserva_ordem_em_batches(monkeypatch):
    import src.embeddings.run as embeddings_run

    class FakeEmbedder:
        provider = "fake"
        model_name = "fake-model"
        dimension = 2

        def embed_documents(self, texts):
            return [
                [float(len(text)), float(index)]
                for index, text in enumerate(texts)
            ]

    monkeypatch.setattr(
        embeddings_run,
        "build_embedder",
        lambda provider, model_name: FakeEmbedder(),
    )

    result = embeddings_run.gerar_embeddings_chunks(
        _chunks_df(), provider="hash", model_name="hash", batch_size=2
    )

    assert result.vectors.shape == (3, 2)
    assert result.metadata["chunk_id"].tolist() == [
        "doc-1::markdown::fixed-size::0000",
        "doc-2::markdown::fixed-size::0000",
        "doc-3::markdown::fixed-size::0000",
    ]
    assert result.manifest["num_chunks"] == 3


def test_gerar_embeddings_chunks_rejeita_texto_vazio():
    from src.embeddings.run import gerar_embeddings_chunks

    df = _chunks_df()
    df.loc[0, "texto"] = ""

    with pytest.raises(RuntimeError, match="texto vazio"):
        gerar_embeddings_chunks(df, provider="hash", model_name="hash")
