"""Metadata e validação da vector store FAISS da Camada 2.3.

Cada vector store é um par inseparável `(index.faiss, metadata.parquet)`.
A linha `i` do metadata corresponde à posição `i` no FAISS. Se essa ordem
quebrar, o sistema vai citar texto errado mesmo recuperando o vetor certo.
Para um corpus jurídico/regulatório isso é grave — daí a validação dura.

Para `chunk_strategy == "hierarchical-child"` também é gerado `parents.parquet`,
um pacote autocontido para a Camada 3 expandir contexto sem precisar baixar
o dataset completo de chunks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.embeddings.embedder import OPENAI_EMBEDDING_DIMENSIONS
from src.vectorstore.manifest import hash_chunk_ids

METADATA_FILENAME = "metadata.parquet"
PARENTS_FILENAME = "parents.parquet"

# Colunas mínimas que a Camada 3 precisa para responder com citação.
METADATA_COLUMNS = [
    "chunk_id",
    "document_id",
    "parent_chunk_id",
    "chunk_strategy",
    "chunk_level",
    "chunk_index",
    "metodo_extracao",
    "extrator",
    "texto",
    "secao",
    "artigo",
    "paragrafo",
    "inciso",
    "alinea",
    "citation_label",
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "assunto",
    "situacao",
    "fonte",
    "formato_original",
    "url_original",
    "url_consolidado",
    "qualidade_extracao",
]

# Coluna que precisa estar não-nula nos chunks pais para a expansão funcionar.
PARENTS_COLUMNS = METADATA_COLUMNS  # mesmo schema; pais são chunks também.


def build_metadata_df(df_chunks: pd.DataFrame) -> pd.DataFrame:
    """Projeta `df_chunks` para o schema mínimo do metadata, preservando ordem.

    A ordem das linhas DEVE ser idêntica à ordem dos vetores indexados.
    Por isso o caller passa `df_chunks` na mesma ordem em que gerou os
    embeddings — esta função só projeta colunas, nunca reordena.
    """
    if df_chunks.empty:
        raise ValueError("df_chunks vazio: não há metadata para construir.")

    missing = [col for col in METADATA_COLUMNS if col not in df_chunks.columns]
    if missing:
        raise RuntimeError(
            f"Chunks sem colunas obrigatórias para metadata: {missing}"
        )

    metadata = df_chunks[METADATA_COLUMNS].reset_index(drop=True).copy()
    return metadata


def build_parents_df(
    df_metadata: pd.DataFrame,
    df_chunks_corpus: pd.DataFrame,
) -> pd.DataFrame:
    """Extrai os chunks pais referenciados pelos filhos indexados.

    `df_metadata` é o metadata dos filhos (já alinhado ao índice FAISS).
    `df_chunks_corpus` é o universo de chunks publicados no Hub, do qual
    extraímos os pais com `chunk_strategy == "hierarchical"`.
    """
    parent_ids = (
        df_metadata["parent_chunk_id"]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    parent_ids = parent_ids[parent_ids.ne("")]
    parent_ids_unicos = sorted(set(parent_ids))
    if not parent_ids_unicos:
        raise RuntimeError(
            "hierarchical-child sem parent_chunk_id preenchido: "
            "verifique a publicação dos chunks pais."
        )

    candidatos = df_chunks_corpus[
        df_chunks_corpus["chunk_strategy"] == "hierarchical"
    ]
    parents = candidatos[candidatos["chunk_id"].isin(parent_ids_unicos)].copy()

    missing = sorted(set(parent_ids_unicos) - set(parents["chunk_id"]))
    if missing:
        raise RuntimeError(
            "Chunks pais referenciados não encontrados no corpus: "
            f"{missing[:10]}"
        )

    parents = parents.drop_duplicates(subset=["chunk_id"]).reset_index(drop=True)
    missing_cols = [col for col in PARENTS_COLUMNS if col not in parents.columns]
    if missing_cols:
        raise RuntimeError(
            f"Pais sem colunas obrigatórias: {missing_cols}"
        )
    return parents[PARENTS_COLUMNS].copy()


def save_metadata(directory: str | Path, df_metadata: pd.DataFrame) -> Path:
    """Persiste `metadata.parquet`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / METADATA_FILENAME
    df_metadata.to_parquet(path, index=False, engine="pyarrow")
    return path


def save_parents(directory: str | Path, df_parents: pd.DataFrame) -> Path:
    """Persiste `parents.parquet` (apenas para hierarchical-child)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / PARENTS_FILENAME
    df_parents.to_parquet(path, index=False, engine="pyarrow")
    return path


def load_metadata(directory: str | Path) -> pd.DataFrame:
    """Carrega `metadata.parquet`."""
    path = Path(directory) / METADATA_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"metadata.parquet não encontrado em {directory}."
        )
    return pd.read_parquet(path, engine="pyarrow")


def load_parents(directory: str | Path) -> pd.DataFrame | None:
    """Carrega `parents.parquet` se existir; senão retorna None."""
    path = Path(directory) / PARENTS_FILENAME
    if not path.exists():
        return None
    return pd.read_parquet(path, engine="pyarrow")


def validar_vectorstore(
    *,
    ntotal: int,
    dimension: int,
    metadata: pd.DataFrame,
    manifest: dict[str, Any],
    parents: pd.DataFrame | None = None,
) -> None:
    """Gate de integridade antes de salvar localmente ou publicar no Hub.

    Cobre: alinhamento ordem-vetor↔ordem-metadata, unicidade de chunk_id,
    textos não vazios, compatibilidade entre dimensão e modelo do manifest,
    e — para hierarchical-child — fechamento das referências pai/filho.
    """
    if ntotal != len(metadata):
        raise RuntimeError(
            f"FAISS ntotal={ntotal} != len(metadata)={len(metadata)}. "
            "Ordem invariante violada."
        )

    manifest_count = int(manifest["count"])
    if manifest_count != len(metadata):
        raise RuntimeError(
            f"manifest.count={manifest_count} != len(metadata)={len(metadata)}. "
            "Vector store e metadata foram gerados com contagens diferentes."
        )

    metadata_hash = hash_chunk_ids(metadata["chunk_id"].astype(str).tolist())
    manifest_hash = manifest.get("chunk_ids_hash")
    if manifest_hash != metadata_hash:
        raise RuntimeError(
            "chunk_ids_hash do manifest diverge da ordem de metadata. "
            "A correspondência vetor↔chunk pode estar quebrada."
        )

    if dimension != int(manifest["dimension"]):
        raise RuntimeError(
            f"Dimensão do índice ({dimension}) divergente do manifest "
            f"({manifest['dimension']})."
        )

    provider = manifest.get("provider")
    model = manifest.get("model")
    if provider == "openai":
        expected = OPENAI_EMBEDDING_DIMENSIONS.get(model)
        if expected is None:
            raise RuntimeError(
                f"Modelo OpenAI desconhecido no manifest: {model!r}"
            )
        if expected != dimension:
            raise RuntimeError(
                f"Modelo {model} espera dimensão {expected}, "
                f"índice tem {dimension}."
            )

    if metadata["chunk_id"].isna().any():
        raise RuntimeError("metadata contém chunk_id nulo.")

    duplicados = metadata[metadata.duplicated(subset=["chunk_id"], keep=False)]
    if len(duplicados) > 0:
        ids = duplicados["chunk_id"].drop_duplicates().tolist()[:10]
        raise RuntimeError(f"chunk_id duplicado em metadata: {ids}")

    texto_vazio = (
        metadata["texto"].fillna("").astype(str).str.strip().eq("")
    )
    if texto_vazio.any():
        ids = metadata.loc[texto_vazio, "chunk_id"].tolist()[:10]
        raise RuntimeError(f"metadata com texto vazio: {ids}")

    strategy = manifest.get("chunk_strategy")
    if strategy == "hierarchical-child":
        if parents is None or parents.empty:
            raise RuntimeError(
                "hierarchical-child exige parents.parquet com pelo menos um pai."
            )
        if parents["chunk_id"].duplicated().any():
            raise RuntimeError("parents.parquet com chunk_id duplicado.")

        parents_texto_vazio = (
            parents["texto"].fillna("").astype(str).str.strip().eq("")
        )
        if parents_texto_vazio.any():
            ids = parents.loc[parents_texto_vazio, "chunk_id"].tolist()[:10]
            raise RuntimeError(f"parents com texto vazio: {ids}")

        parent_ids = set(parents["chunk_id"].astype(str))
        referenciados = (
            metadata["parent_chunk_id"]
            .dropna()
            .astype(str)
            .map(str.strip)
        )
        referenciados = referenciados[referenciados.ne("")]
        if referenciados.empty:
            raise RuntimeError(
                "hierarchical-child sem parent_chunk_id preenchido em metadata."
            )
        orfaos = sorted(set(referenciados) - parent_ids)
        if orfaos:
            raise RuntimeError(
                f"parent_chunk_id sem pai em parents.parquet: {orfaos[:10]}"
            )
