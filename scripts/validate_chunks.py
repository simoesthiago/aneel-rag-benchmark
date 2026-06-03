#!/usr/bin/env python3
"""Valida chunks publicados no HuggingFace Hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como `python scripts/validate_chunks.py` na raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.chunking.common import validar_chunks  # noqa: E402
from src.chunking.hub import carregar_chunks_hub  # noqa: E402
from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402


def validar_chunks_publicados(repo_id: str) -> int:
    """Carrega chunks/documents do Hub e imprime métricas de qualidade."""
    print(f"Carregando corpus e chunks de {repo_id}...")
    df_documents: pd.DataFrame = carregar_corpus_hub(repo_id)
    df_chunks: pd.DataFrame = carregar_chunks_hub(repo_id)

    validar_chunks(df_chunks, df_documents)

    print(f"\nTOTAL: {len(df_chunks)} chunks")
    print("\nPor estrategia/metodo/tipo:")
    print(
        df_chunks.groupby(["chunk_strategy", "metodo_extracao", "tipo"])
        .size()
        .to_string()
    )

    print("\nChunks por metodo_extracao:")
    print(df_chunks["metodo_extracao"].value_counts().to_string())

    print("\n✅ Validação de chunks OK.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida chunks no HF Hub")
    parser.add_argument("--repo", default=HF_DATASET_REPO)
    args = parser.parse_args()
    return validar_chunks_publicados(args.repo)


if __name__ == "__main__":
    sys.exit(main())
