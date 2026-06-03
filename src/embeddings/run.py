"""CLI da Camada 2.2 para gerar embeddings sobre chunks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.chunking.hub import carregar_chunks_hub
from src.config.settings import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    HF_DATASET_REPO,
)
from src.embeddings.embedder import (
    MAX_OPENAI_BATCH_ITEMS,
    OPENAI_EMBEDDING_DIMENSIONS,
    build_embedder,
)


@dataclass
class EmbeddingRunResult:
    """Resultado em memória da geração de embeddings."""

    vectors: np.ndarray
    metadata: pd.DataFrame
    manifest: dict[str, Any]


def gerar_embeddings_chunks(
    df_chunks: pd.DataFrame,
    *,
    provider: str = EMBEDDING_PROVIDER,
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> EmbeddingRunResult:
    """Gera embeddings sobre `chunk["texto"]`, preservando ordem por chunk."""
    _validar_batch_size(batch_size)
    _validar_chunks_para_embedding(df_chunks)

    embedder = build_embedder(provider=provider, model_name=model_name)
    embeddings: list[list[float]] = []
    texts = df_chunks["texto"].astype(str).tolist()

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        embeddings.extend(embedder.embed_documents(batch))

    vectors = np.array(embeddings, dtype="float32")
    if vectors.shape != (len(df_chunks), embedder.dimension):
        raise RuntimeError(
            "Shape inesperado dos embeddings: "
            f"{vectors.shape}; esperado=({len(df_chunks)}, "
            f"{embedder.dimension})"
        )

    manifest = {
        "provider": embedder.provider,
        "model": embedder.model_name,
        "dimension": embedder.dimension,
        "batch_size": batch_size,
        "num_chunks": len(df_chunks),
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "chunk_strategy": sorted(
            df_chunks["chunk_strategy"].dropna().astype(str).unique()
        ),
        "metodo_extracao": sorted(
            df_chunks["metodo_extracao"].dropna().astype(str).unique()
        ),
        "tipo": sorted(df_chunks["tipo"].dropna().astype(str).unique()),
    }
    return EmbeddingRunResult(
        vectors=vectors,
        metadata=df_chunks.reset_index(drop=True).copy(),
        manifest=manifest,
    )


def main() -> None:
    """Entrada de linha de comando para geração de embeddings."""
    args = _parse_args()
    df_chunks = carregar_chunks_hub(args.repo_id)
    df_chunks = _filtrar_chunks(
        df_chunks,
        chunk_strategy=args.chunk_strategy,
        metodo_extracao=args.metodo_extracao,
        tipo=args.tipo,
        amostra=args.amostra,
    )
    print(f"Gerando embeddings para {len(df_chunks)} chunks...")

    result = gerar_embeddings_chunks(
        df_chunks,
        provider=args.provider,
        model_name=args.model,
        batch_size=args.batch_size,
    )
    _imprimir_resumo(result)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera embeddings em memória sobre chunks publicados."
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "hash"],
        default=EMBEDDING_PROVIDER,
        help="Provider de embeddings.",
    )
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL,
        choices=sorted(OPENAI_EMBEDDING_DIMENSIONS),
        help="Modelo OpenAI de embeddings. Ignorado para provider=hash.",
    )
    parser.add_argument(
        "--chunk-strategy",
        choices=[
            "fixed-size",
            "article-aware",
            "hierarchical",
            "hierarchical-child",
        ],
        required=True,
        help="Estratégia de chunks a embutir.",
    )
    parser.add_argument(
        "--metodo-extracao",
        choices=["texto", "markdown"],
        required=True,
        help="Formato de saída da Camada 1.",
    )
    parser.add_argument(
        "--tipo",
        choices=["ato_normativo", "procedimento", "manual", "lei"],
        default=None,
        help="Filtro opcional por tipo documental.",
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=None,
        help="Usa apenas os primeiros N chunks apos o filtro.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=EMBEDDING_BATCH_SIZE,
        help="Quantidade de chunks por chamada de embedding.",
    )
    parser.add_argument(
        "--repo-id",
        default=HF_DATASET_REPO,
        help="Dataset do HuggingFace Hub com data/chunks/.",
    )
    return parser.parse_args()


def _filtrar_chunks(
    df_chunks: pd.DataFrame,
    *,
    chunk_strategy: str,
    metodo_extracao: str,
    tipo: str | None,
    amostra: int | None,
) -> pd.DataFrame:
    filtered = df_chunks[
        (df_chunks["chunk_strategy"] == chunk_strategy)
        & (df_chunks["metodo_extracao"] == metodo_extracao)
    ].copy()
    if tipo is not None:
        filtered = filtered[filtered["tipo"] == tipo].copy()
    if amostra is not None:
        if amostra <= 0:
            raise ValueError("--amostra deve ser maior que zero")
        filtered = filtered.head(amostra).copy()
    if filtered.empty:
        raise RuntimeError("Filtro selecionado nao retornou chunks.")
    return filtered.reset_index(drop=True)


def _validar_chunks_para_embedding(df_chunks: pd.DataFrame) -> None:
    missing = {
        "chunk_id",
        "texto",
        "chunk_strategy",
        "metodo_extracao",
        "tipo",
    }
    missing = missing - set(df_chunks.columns)
    if missing:
        raise RuntimeError(
            f"Chunks sem colunas obrigatórias: {sorted(missing)}"
        )

    empty = df_chunks["texto"].fillna("").astype(str).str.strip().eq("")
    if empty.any():
        ids = df_chunks.loc[empty, "chunk_id"].tolist()[:10]
        raise RuntimeError(f"Chunks com texto vazio: {ids}")


def _validar_batch_size(batch_size: int) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    if batch_size > MAX_OPENAI_BATCH_ITEMS:
        raise ValueError(
            f"batch_size={batch_size} excede o limite de "
            f"{MAX_OPENAI_BATCH_ITEMS} itens por chamada."
        )


def _imprimir_resumo(result: EmbeddingRunResult) -> None:
    print("\nResumo de embeddings:")
    print(f"  Shape: {result.vectors.shape}")
    print("  Manifest:")
    for key, value in result.manifest.items():
        print(f"    {key}: {value}")


if __name__ == "__main__":
    main()
