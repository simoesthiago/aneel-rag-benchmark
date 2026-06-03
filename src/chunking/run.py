"""CLI para gerar e publicar chunks derivados do corpus ANEEL."""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
from huggingface_hub import HfApi

from src.chunking.article_aware import chunk_article_aware
from src.chunking.common import CHUNK_SCHEMA_COLUMNS, validar_chunks
from src.chunking.fixed_size import chunk_fixed_size
from src.chunking.hierarchical import chunk_parent_child
from src.config.settings import HF_DATASET_REPO, get_hf_token
from src.ingestion.uploader import carregar_corpus_hub

Chunker = Callable[[dict[str, Any]], list[dict[str, Any]]]

STRATEGY_BUILDERS: dict[str, Chunker] = {
    "fixed-size": chunk_fixed_size,
    "article-aware": chunk_article_aware,
    "hierarchical": chunk_parent_child,
}


def gerar_chunks(
    df_documents: pd.DataFrame,
    *,
    estrategia: str = "todas",
) -> pd.DataFrame:
    """
    Gera chunks para uma ou todas as estrategias configuradas.

    A entrada e o DataFrame de documentos da Camada 1. A saida e uma tabela
    derivada; ela nunca substitui `documents`, apenas prepara o retrieval.
    """
    estrategias = _estrategias_selecionadas(estrategia)
    records: list[dict[str, Any]] = []
    documents = df_documents.to_dict("records")

    for nome in estrategias:
        chunker = STRATEGY_BUILDERS[nome]
        for document in documents:
            records.extend(chunker(document))

    df_chunks = pd.DataFrame(records)
    if df_chunks.empty:
        raise RuntimeError(
            "Nenhum chunk foi gerado; verifique o corpus de entrada."
        )

    for col in CHUNK_SCHEMA_COLUMNS:
        if col not in df_chunks.columns:
            df_chunks[col] = None

    df_chunks = df_chunks[CHUNK_SCHEMA_COLUMNS]
    validar_chunks(df_chunks, df_documents)
    return df_chunks


def publicar_chunks(
    df_chunks: pd.DataFrame,
    *,
    repo_id: str | None = None,
) -> str:
    """
    Publica chunks no mesmo dataset do corpus, preservando `data/documents/`.

    O upload substitui apenas `data/chunks/`, porque os chunks sao artefato
    derivado da Camada 2 e podem ser regenerados sem tocar na ingestao.
    """
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    token = get_hf_token()
    api = HfApi(token=token)

    with tempfile.TemporaryDirectory() as tmpdir:
        for (strategy, metodo, tipo), df_part in df_chunks.groupby(
            ["chunk_strategy", "metodo_extracao", "tipo"], dropna=False
        ):
            part_dir = os.path.join(
                tmpdir,
                "data",
                "chunks",
                f"chunk_strategy={strategy}",
                f"metodo_extracao={metodo}",
                f"tipo={tipo}",
            )
            os.makedirs(part_dir, exist_ok=True)
            path = os.path.join(part_dir, "part-0.parquet")
            df_part.drop(
                columns=["chunk_strategy", "metodo_extracao", "tipo"]
            ).to_parquet(path, index=False, engine="pyarrow")
            print(
                f"  chunk_strategy={strategy} / metodo={metodo} "
                f"/ tipo={tipo}: "
                f"{len(df_part)} chunks"
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_msg = (
            f"Atualizacao de chunks: {len(df_chunks)} chunks ({timestamp})"
        )

        print(f"\n  Fazendo upload de chunks para {repo_id}...")
        api.upload_folder(
            folder_path=tmpdir,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=commit_msg,
            delete_patterns=["data/chunks/"],
        )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  Upload concluido: {url}")
    return url


def main() -> None:
    """Entrada de linha de comando para a Camada 2.1."""
    args = _parse_args()
    df_documents = carregar_corpus_hub(args.repo_id)
    df_documents = _filtrar_documentos(
        df_documents,
        metodo_extracao=args.metodo_extracao,
        amostra=args.amostra,
    )
    print(f"Gerando chunks para {len(df_documents)} documentos...")

    df_chunks = gerar_chunks(df_documents, estrategia=args.estrategia)
    _imprimir_resumo(df_chunks)

    if args.publicar:
        publicar_chunks(df_chunks, repo_id=args.repo_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gera chunks derivados do corpus ANEEL publicado no HF Hub."
        )
    )
    parser.add_argument(
        "--estrategia",
        choices=["fixed-size", "article-aware", "hierarchical", "todas"],
        default="todas",
        help="Estrategia de chunking a gerar.",
    )
    parser.add_argument(
        "--metodo-extracao",
        choices=["texto", "markdown", "todos"],
        default="todos",
        help="Filtra documentos por formato de saida da Camada 1.",
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=None,
        help="Usa apenas os primeiros N documentos apos o filtro.",
    )
    parser.add_argument(
        "--repo-id",
        default=HF_DATASET_REPO,
        help="Dataset do HuggingFace Hub com data/documents/.",
    )
    parser.add_argument(
        "--publicar",
        action="store_true",
        help="Publica os chunks em data/chunks/ no mesmo dataset.",
    )
    return parser.parse_args()


def _estrategias_selecionadas(estrategia: str) -> list[str]:
    if estrategia == "todas":
        return list(STRATEGY_BUILDERS)
    if estrategia not in STRATEGY_BUILDERS:
        raise ValueError(f"Estrategia desconhecida: {estrategia}")
    return [estrategia]


def _filtrar_documentos(
    df_documents: pd.DataFrame,
    *,
    metodo_extracao: str,
    amostra: int | None,
) -> pd.DataFrame:
    if metodo_extracao != "todos":
        df_documents = df_documents[
            df_documents["metodo_extracao"] == metodo_extracao
        ].copy()
    if amostra is not None:
        if amostra <= 0:
            raise ValueError("--amostra deve ser maior que zero")
        df_documents = df_documents.head(amostra).copy()
    if df_documents.empty:
        raise RuntimeError("Filtro selecionado nao retornou documentos.")
    return df_documents.reset_index(drop=True)


def _imprimir_resumo(df_chunks: pd.DataFrame) -> None:
    print("\nResumo de chunks:")
    print(f"  Total: {len(df_chunks)}")
    print("\nPor estrategia/metodo/tipo:")
    print(
        df_chunks.groupby(["chunk_strategy", "metodo_extracao", "tipo"])
        .size()
        .to_string()
    )


if __name__ == "__main__":
    main()
