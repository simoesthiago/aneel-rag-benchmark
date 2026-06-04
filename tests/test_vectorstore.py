"""Testes da Camada 2.3 — vector store FAISS persistente."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.vectorstore.faiss_store import FAISSVectorStore, normalize
from src.vectorstore.hub import vectorstore_artifacts_present
from src.vectorstore.manifest import build_manifest, load_manifest, save_manifest
from src.vectorstore.metadata import (
    build_metadata_df,
    build_parents_df,
    load_metadata,
    load_parents,
    save_metadata,
    save_parents,
    validar_vectorstore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _chunk_row(
    *,
    chunk_id: str,
    document_id: str = "ren-2021-1000",
    parent_chunk_id: str | None = None,
    chunk_strategy: str = "article-aware",
    chunk_level: str = "leaf",
    chunk_index: int = 0,
    texto: str = "texto do chunk",
    metodo_extracao: str = "markdown",
    tipo: str = "ato_normativo",
    titulo: str = "REN 1000/2021",
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "parent_chunk_id": parent_chunk_id,
        "chunk_strategy": chunk_strategy,
        "chunk_level": chunk_level,
        "chunk_index": chunk_index,
        "texto": texto,
        "metodo_extracao": metodo_extracao,
        "extrator": "pymupdf4llm",
        "secao": None,
        "artigo": None,
        "paragrafo": None,
        "inciso": None,
        "alinea": None,
        "citation_label": f"{titulo}, chunk {chunk_index}",
        "tipo": tipo,
        "subtipo": "ren",
        "numero": "1000",
        "ano": 2021,
        "titulo": titulo,
        "assunto": "tarifa",
        "situacao": "vigente",
        "fonte": "cedoc",
        "formato_original": "pdf",
        "qualidade_extracao": 1.0,
        "url_original": "https://www2.aneel.gov.br/cedoc/ren20211000.pdf",
        "url_consolidado": "https://www2.aneel.gov.br/cedoc/bren20211000.pdf",
    }


def _chunks_df_simples() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _chunk_row(
                chunk_id="doc-1::markdown::article-aware::0000",
                document_id="doc-1",
                chunk_index=0,
                texto="tarifa de distribuicao revisao tarifaria periodica",
            ),
            _chunk_row(
                chunk_id="doc-1::markdown::article-aware::0001",
                document_id="doc-1",
                chunk_index=1,
                texto="modicidade tarifaria base regulatoria remuneracao",
            ),
            _chunk_row(
                chunk_id="doc-2::markdown::article-aware::0000",
                document_id="doc-2",
                chunk_index=0,
                texto="penalidade infracao fiscalizacao auto",
            ),
        ]
    )


def _chunks_df_hierarchical() -> pd.DataFrame:
    """Pais + filhos para testar parents.parquet."""
    pai = _chunk_row(
        chunk_id="doc-1::markdown::hierarchical::0000",
        document_id="doc-1",
        chunk_strategy="hierarchical",
        chunk_level="parent",
        chunk_index=0,
        texto="texto completo do artigo pai",
    )
    filhos = [
        _chunk_row(
            chunk_id="doc-1::markdown::hierarchical-child::0000",
            document_id="doc-1",
            parent_chunk_id="doc-1::markdown::hierarchical::0000",
            chunk_strategy="hierarchical-child",
            chunk_level="child",
            chunk_index=0,
            texto="primeiro filho do artigo",
        ),
        _chunk_row(
            chunk_id="doc-1::markdown::hierarchical-child::0001",
            document_id="doc-1",
            parent_chunk_id="doc-1::markdown::hierarchical::0000",
            chunk_strategy="hierarchical-child",
            chunk_level="child",
            chunk_index=1,
            texto="segundo filho do artigo",
        ),
    ]
    return pd.DataFrame([pai] + filhos)


# ---------------------------------------------------------------------------
# 1, 2, 3, 4. FAISSVectorStore — build, normalização, search, dimensão
# ---------------------------------------------------------------------------

def test_faiss_store_build_cria_indice_com_dimensao_correta():
    vectors = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype="float32"
    )
    store = FAISSVectorStore(dimension=3).build(vectors)

    assert store.ntotal == 3
    assert store.dimension == 3


def test_normalize_aplica_l2_unitario():
    vectors = [[3.0, 4.0], [1.0, 0.0], [0.0, 2.0]]

    normalized = normalize(vectors)

    norms = np.linalg.norm(normalized, axis=1)
    assert np.allclose(norms, [1.0, 1.0, 1.0])


def test_search_retorna_vetor_mais_similar_no_topo():
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.9, 0.1, 0.0],  # parecido com vector[0]
        ],
        dtype="float32",
    )
    store = FAISSVectorStore(dimension=3).build(vectors)
    query = np.array([1.0, 0.0, 0.0], dtype="float32")

    scores, indices = store.search(query, top_k=2)

    assert indices.shape == (1, 2)
    assert indices[0][0] == 0
    assert indices[0][1] == 2
    # Inner product entre vetores unitários ∈ [-1, 1].
    assert pytest.approx(float(scores[0][0]), abs=1e-5) == 1.0


def test_faiss_store_rejeita_dimensao_errada():
    store = FAISSVectorStore(dimension=3).build(
        np.array([[1.0, 0.0, 0.0]], dtype="float32")
    )

    with pytest.raises(ValueError, match="Dimensão da consulta"):
        store.search(np.array([1.0, 0.0], dtype="float32"))


def test_faiss_store_build_rejeita_dimensao_divergente_dos_vetores():
    with pytest.raises(ValueError, match="Dimensão dos vetores"):
        FAISSVectorStore(dimension=4).build(
            np.array([[1.0, 0.0, 0.0]], dtype="float32")
        )


# ---------------------------------------------------------------------------
# 5. Validação de alinhamento metadata ↔ índice
# ---------------------------------------------------------------------------

def test_validar_vectorstore_rejeita_metadata_desalinhada():
    df_chunks = _chunks_df_simples()
    metadata = build_metadata_df(df_chunks)
    manifest = build_manifest(
        provider="hash",
        model="hash",
        dimension=8,
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        count=len(metadata),
        chunk_ids=metadata["chunk_id"].tolist(),
        corpus_repo="simoesthiago/aneel-corpus",
    )

    with pytest.raises(RuntimeError, match="Ordem invariante violada"):
        validar_vectorstore(
            ntotal=2,  # mentindo: índice teria 2, metadata tem 3
            dimension=8,
            metadata=metadata,
            manifest=manifest,
        )


def test_validar_vectorstore_rejeita_metadata_com_ordem_divergente():
    df_chunks = _chunks_df_simples()
    metadata = build_metadata_df(df_chunks)
    manifest = build_manifest(
        provider="hash",
        model="hash",
        dimension=8,
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        count=len(metadata),
        chunk_ids=metadata["chunk_id"].tolist(),
        corpus_repo="simoesthiago/aneel-corpus",
    )
    metadata_embaralhado = metadata.iloc[::-1].reset_index(drop=True)

    with pytest.raises(RuntimeError, match="chunk_ids_hash"):
        validar_vectorstore(
            ntotal=len(metadata_embaralhado),
            dimension=8,
            metadata=metadata_embaralhado,
            manifest=manifest,
        )


def test_validar_vectorstore_rejeita_dimensao_incompativel_com_modelo():
    df_chunks = _chunks_df_simples()
    metadata = build_metadata_df(df_chunks)
    manifest = build_manifest(
        provider="openai",
        model="text-embedding-3-large",  # dim esperada = 3072
        dimension=1536,                   # divergente
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        count=len(metadata),
        chunk_ids=metadata["chunk_id"].tolist(),
        corpus_repo="simoesthiago/aneel-corpus",
    )

    with pytest.raises(RuntimeError, match="text-embedding-3-large"):
        validar_vectorstore(
            ntotal=len(metadata),
            dimension=1536,
            metadata=metadata,
            manifest=manifest,
        )


# ---------------------------------------------------------------------------
# 6. Manifest — round-trip preserva campos
# ---------------------------------------------------------------------------

def test_manifest_round_trip_preserva_campos(tmp_path: Path):
    manifest = build_manifest(
        provider="openai",
        model="text-embedding-3-large",
        dimension=3072,
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        count=2,
        chunk_ids=["a::markdown::article-aware::0000",
                   "b::markdown::article-aware::0000"],
        corpus_repo="simoesthiago/aneel-corpus",
        extra={"batch_size": 100},
    )

    save_manifest(tmp_path, manifest)
    loaded = load_manifest(tmp_path)

    assert loaded["provider"] == "openai"
    assert loaded["model"] == "text-embedding-3-large"
    assert loaded["dimension"] == 3072
    assert loaded["count"] == 2
    assert loaded["index_type"] == "IndexFlatIP"
    assert loaded["metric"] == "ip"
    assert loaded["normalized"] is True
    assert loaded["chunk_ids_hash"] == manifest["chunk_ids_hash"]
    assert loaded["extra"]["batch_size"] == 100


def test_manifest_rejeita_count_divergente_dos_chunk_ids():
    with pytest.raises(ValueError, match="count="):
        build_manifest(
            provider="hash",
            model="hash",
            dimension=8,
            chunk_strategy="article-aware",
            metodo_extracao="markdown",
            count=5,
            chunk_ids=["a", "b", "c"],
            corpus_repo="simoesthiago/aneel-corpus",
        )


# ---------------------------------------------------------------------------
# 7. hierarchical-child — parents.parquet + validação child→parent
# ---------------------------------------------------------------------------

def test_build_parents_df_extrai_pais_referenciados():
    df = _chunks_df_hierarchical()
    filhos = df[df["chunk_strategy"] == "hierarchical-child"].reset_index(
        drop=True
    )
    metadata = build_metadata_df(filhos)

    parents = build_parents_df(metadata, df)

    assert len(parents) == 1
    assert parents.iloc[0]["chunk_id"] == "doc-1::markdown::hierarchical::0000"


def test_validar_vectorstore_rejeita_parent_orfao():
    df = _chunks_df_hierarchical()
    filhos = df[df["chunk_strategy"] == "hierarchical-child"].reset_index(
        drop=True
    )
    metadata = build_metadata_df(filhos)

    # parents incompleto — propositalmente vazio para forçar o erro
    parents_vazio = (
        df[df["chunk_strategy"] == "hierarchical"]
        .iloc[0:0]
        .reset_index(drop=True)
    )

    manifest = build_manifest(
        provider="hash",
        model="hash",
        dimension=8,
        chunk_strategy="hierarchical-child",
        metodo_extracao="markdown",
        count=len(metadata),
        chunk_ids=metadata["chunk_id"].tolist(),
        corpus_repo="simoesthiago/aneel-corpus",
    )

    with pytest.raises(RuntimeError, match="hierarchical-child"):
        validar_vectorstore(
            ntotal=len(metadata),
            dimension=8,
            metadata=metadata,
            manifest=manifest,
            parents=parents_vazio,
        )


# ---------------------------------------------------------------------------
# 8. Fluxo ponta-a-ponta com provider=hash (sem API; rede mockada)
# ---------------------------------------------------------------------------

def test_run_ponta_a_ponta_com_hash(tmp_path: Path, monkeypatch):
    from src.vectorstore import run as vectorstore_run

    df = _chunks_df_simples()

    # `carregar_chunks_hub` faria chamada de rede — interceptamos com fixture.
    monkeypatch.setattr(
        vectorstore_run, "carregar_chunks_hub", lambda repo_id: df
    )

    output_dir = tmp_path / "vs"
    args = [
        "vectorstore.run",
        "--provider", "hash",
        "--model", "text-embedding-3-small",  # ignorado para hash
        "--chunk-strategy", "article-aware",
        "--metodo-extracao", "markdown",
        "--batch-size", "2",
        "--output-dir", str(output_dir),
    ]
    monkeypatch.setattr("sys.argv", args)

    exit_code = vectorstore_run.main()

    assert exit_code == 0
    assert vectorstore_artifacts_present(output_dir)

    manifest = load_manifest(output_dir)
    metadata = load_metadata(output_dir)
    parents = load_parents(output_dir)

    assert manifest["provider"] == "hash"
    assert manifest["chunk_strategy"] == "article-aware"
    assert manifest["count"] == 3
    assert len(metadata) == 3
    assert parents is None  # article-aware não gera parents

    # Sanidade: reload do índice retorna ntotal correto
    store = FAISSVectorStore.load(output_dir)
    assert store.ntotal == 3


def test_run_hash_sem_output_dir_usa_modelo_hash_no_path(tmp_path: Path, monkeypatch):
    from src.vectorstore import run as vectorstore_run

    df = _chunks_df_simples()
    monkeypatch.setattr(
        vectorstore_run, "carregar_chunks_hub", lambda repo_id: df
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "vectorstore.run",
            "--provider", "hash",
            "--model", "text-embedding-3-large",
            "--chunk-strategy", "article-aware",
            "--metodo-extracao", "markdown",
        ],
    )

    exit_code = vectorstore_run.main()

    expected = (
        tmp_path
        / ".artifacts"
        / "vectorstores"
        / "hash"
        / "hash"
        / "article-aware"
        / "markdown"
    )
    assert exit_code == 0
    assert vectorstore_artifacts_present(expected)
    assert load_manifest(expected)["model"] == "hash"


def test_run_hierarchical_child_gera_parents(tmp_path: Path, monkeypatch):
    from src.vectorstore import run as vectorstore_run

    df = _chunks_df_hierarchical()
    monkeypatch.setattr(
        vectorstore_run, "carregar_chunks_hub", lambda repo_id: df
    )

    output_dir = tmp_path / "vs-hc"
    args = [
        "vectorstore.run",
        "--provider", "hash",
        "--chunk-strategy", "hierarchical-child",
        "--metodo-extracao", "markdown",
        "--batch-size", "2",
        "--output-dir", str(output_dir),
    ]
    monkeypatch.setattr("sys.argv", args)

    exit_code = vectorstore_run.main()

    assert exit_code == 0
    parents = load_parents(output_dir)
    assert parents is not None
    assert len(parents) == 1
    assert parents.iloc[0]["chunk_id"] == "doc-1::markdown::hierarchical::0000"


# ---------------------------------------------------------------------------
# Round-trip do índice e do metadata em disco
# ---------------------------------------------------------------------------

def test_save_load_index_metadata_parents(tmp_path: Path):
    vectors = np.array(
        [[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]], dtype="float32"
    )
    store = FAISSVectorStore(dimension=2).build(vectors)
    store.save(tmp_path)

    loaded = FAISSVectorStore.load(tmp_path)
    assert loaded.ntotal == 3
    assert loaded.dimension == 2

    df = _chunks_df_simples()
    metadata = build_metadata_df(df)
    save_metadata(tmp_path, metadata)
    loaded_meta = load_metadata(tmp_path)
    pd.testing.assert_frame_equal(metadata, loaded_meta)

    parents = build_parents_df(
        build_metadata_df(
            _chunks_df_hierarchical().query(
                "chunk_strategy == 'hierarchical-child'"
            ).reset_index(drop=True)
        ),
        _chunks_df_hierarchical(),
    )
    save_parents(tmp_path, parents)
    loaded_parents = load_parents(tmp_path)
    assert loaded_parents is not None
    pd.testing.assert_frame_equal(parents, loaded_parents)
