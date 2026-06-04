#!/usr/bin/env python3
"""Valida uma vector store FAISS publicada no HuggingFace Hub.

Baixa do Hub, roda `validar_vectorstore` e executa 5 consultas-canário
para confirmar que o índice está retornando chunks relevantes para perguntas
típicas do domínio regulatório elétrico.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como `python scripts/validate_vectorstore.py` na raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import (  # noqa: E402
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    HF_DATASET_REPO,
)
from src.embeddings.embedder import build_embedder  # noqa: E402
from src.vectorstore.hub import carregar_vectorstore  # noqa: E402
from src.vectorstore.metadata import validar_vectorstore  # noqa: E402

CONSULTAS_CANARIO = [
    "modicidade tarifária",
    "revisão tarifária periódica",
    "procedimentos de distribuição",
    "suspensão do fornecimento de energia",
    "competência da ANEEL",
]


def main() -> int:
    args = _parse_args()

    pkg = carregar_vectorstore(
        provider=args.provider,
        model=args.model,
        chunk_strategy=args.chunk_strategy,
        metodo_extracao=args.metodo_extracao,
        repo_id=args.repo_id,
    )
    store = pkg["index"]
    metadata = pkg["metadata"]
    parents = pkg["parents"]
    manifest = pkg["manifest"]

    print(
        f"\nVector store baixada: "
        f"provider={args.provider} model={args.model} "
        f"strategy={args.chunk_strategy} metodo={args.metodo_extracao}"
    )
    print(f"  ntotal={store.ntotal} dimension={store.dimension}")
    print(f"  manifest.count={manifest['count']}")

    validar_vectorstore(
        ntotal=store.ntotal,
        dimension=store.dimension,
        metadata=metadata,
        manifest=manifest,
        parents=parents,
    )
    print("  ✅ Validação de integridade OK.")

    embedder = build_embedder(provider=args.provider, model_name=args.model)
    print(
        f"\nConsultas-canário (embedder: {embedder.provider}/"
        f"{embedder.model_name}):"
    )
    for consulta in CONSULTAS_CANARIO:
        query_vector = embedder.embed_query(consulta)
        scores, indices = store.search(query_vector, top_k=3)
        print(f"\n  > {consulta!r}")
        for rank, (score, idx) in enumerate(
            zip(scores[0], indices[0]), start=1
        ):
            if idx < 0:
                continue
            row = metadata.iloc[int(idx)]
            print(
                f"    {rank}. score={float(score):.4f} | "
                f"{row['citation_label']}"
            )

    print("\n✅ Vector store passou no gate de qualidade.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida vector store FAISS publicada no Hub."
    )
    parser.add_argument(
        "--provider",
        default=EMBEDDING_PROVIDER,
        help="Provider de embeddings da vector store.",
    )
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL,
        help="Modelo de embeddings da vector store.",
    )
    parser.add_argument(
        "--chunk-strategy",
        required=True,
        choices=["fixed-size", "article-aware", "hierarchical-child"],
    )
    parser.add_argument(
        "--metodo-extracao",
        required=True,
        choices=["texto", "markdown"],
    )
    parser.add_argument(
        "--repo-id",
        default=HF_DATASET_REPO,
        help="Dataset do Hub com data/vectorstores/.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
