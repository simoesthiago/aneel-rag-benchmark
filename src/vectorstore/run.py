"""CLI da Camada 2.3 — gera, valida e publica uma vector store FAISS.

Fluxo de uma execução:

  1. Carrega chunks do Hub filtrados por `chunk_strategy` e `metodo_extracao`.
  2. Se `chunk_strategy == "hierarchical-child"`, carrega também os chunks
     pais (`chunk_strategy == "hierarchical"`) para montar `parents.parquet`.
  3. Gera embeddings via `build_embedder` (OpenAI ou hash) em batches.
  4. Normaliza, indexa em `IndexFlatIP`, monta metadata na MESMA ordem.
  5. Valida integridade (ordem, dimensão, FKs pai/filho).
  6. Se `--publicar`, faz upload em memória ao HF Hub.
  7. Só grava localmente quando `--output-dir` é passado explicitamente.

A entrega mínima da Camada 2.3 publica apenas
`openai / text-embedding-3-large / article-aware / markdown`.
A matriz das outras 11 vector stores roda depois, com o mesmo CLI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.chunking.hub import carregar_chunks_hub
from src.config.settings import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    FAISS_INDEX_TYPE,
    FAISS_METRIC,
    HF_DATASET_REPO,
)
from src.embeddings.embedder import (
    MAX_OPENAI_BATCH_ITEMS,
    OPENAI_EMBEDDING_DIMENSIONS,
    build_embedder,
)
from src.vectorstore.faiss_store import FAISSVectorStore
from src.vectorstore.hub import (
    publicar_vectorstore_memoria,
    publicar_vectorstore,
    vectorstore_artifacts_present,
    vectorstore_artifacts_present_hub,
)
from src.vectorstore.manifest import (
    build_manifest,
    save_manifest,
)
from src.vectorstore.metadata import (
    build_metadata_df,
    build_parents_df,
    save_metadata,
    save_parents,
    validar_vectorstore,
)

CHUNK_STRATEGIES = ["fixed-size", "article-aware", "hierarchical-child"]
METODOS_EXTRACAO = ["texto", "markdown"]


def construir_vectorstore(
    df_chunks_filtrados: pd.DataFrame,
    df_chunks_corpus: pd.DataFrame,
    *,
    provider: str,
    model_name: str,
    chunk_strategy: str,
    metodo_extracao: str,
    batch_size: int,
    corpus_repo: str,
) -> tuple[FAISSVectorStore, pd.DataFrame, pd.DataFrame | None, dict]:
    """Constrói índice, metadata e (se aplicável) parents — tudo em memória.

    Devolve `(store, metadata, parents_or_None, manifest)` já validado.
    O caller decide se persiste em disco e/ou publica no Hub.
    """
    if df_chunks_filtrados.empty:
        raise RuntimeError("Nenhum chunk após o filtro: nada para indexar.")

    df_chunks_filtrados = df_chunks_filtrados.reset_index(drop=True).copy()
    _validar_chunks_para_indexacao(df_chunks_filtrados)

    embedder = build_embedder(provider=provider, model_name=model_name)
    print(
        f"  Embedder: provider={embedder.provider} "
        f"model={embedder.model_name} dim={embedder.dimension}"
    )

    textos = df_chunks_filtrados["texto"].astype(str).tolist()
    n = len(textos)
    print(f"  Gerando embeddings para {n} chunks em batches de {batch_size}...")

    vetores: list[list[float]] = []
    num_textos_truncados = 0
    for start in range(0, n, batch_size):
        batch = textos[start:start + batch_size]
        vetores.extend(embedder.embed_documents(batch))
        stats = getattr(embedder, "last_truncation_stats", {})
        num_textos_truncados += int(stats.get("num_truncated", 0))
        progresso = min(start + batch_size, n)
        print(f"    {progresso}/{n} chunks embeddings ok")

    if len(vetores) != n:
        raise RuntimeError(
            f"Embedder devolveu {len(vetores)} vetores para {n} chunks."
        )

    store = FAISSVectorStore(dimension=embedder.dimension).build(vetores)
    metadata = build_metadata_df(df_chunks_filtrados)

    parents: pd.DataFrame | None = None
    if chunk_strategy == "hierarchical-child":
        parents = build_parents_df(metadata, df_chunks_corpus)
        print(f"  parents.parquet: {len(parents)} pais únicos")

    manifest = build_manifest(
        provider=embedder.provider,
        model=embedder.model_name,
        dimension=embedder.dimension,
        chunk_strategy=chunk_strategy,
        metodo_extracao=metodo_extracao,
        count=store.ntotal,
        chunk_ids=metadata["chunk_id"].astype(str).tolist(),
        corpus_repo=corpus_repo,
        normalized=True,
        metric=FAISS_METRIC,
        index_type=FAISS_INDEX_TYPE,
        extra={
            "batch_size": batch_size,
            "embedding_texts_truncated": num_textos_truncados,
            "metadata_texto_preservado": True,
        },
    )

    validar_vectorstore(
        ntotal=store.ntotal,
        dimension=store.dimension,
        metadata=metadata,
        manifest=manifest,
        parents=parents,
    )

    return store, metadata, parents, manifest


def persistir_vectorstore(
    output_dir: str | Path,
    *,
    store: FAISSVectorStore,
    metadata: pd.DataFrame,
    parents: pd.DataFrame | None,
    manifest: dict,
) -> Path:
    """Materializa os 3 (ou 4) arquivos da vector store em `output_dir`."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    store.save(output_dir)
    save_metadata(output_dir, metadata)
    save_manifest(output_dir, manifest)
    if parents is not None:
        save_parents(output_dir, parents)
    return output_dir


def main() -> int:
    args = _parse_args()
    effective_model = _effective_model_name(args.provider, args.model)

    if args.skip_existing and args.publicar:
        if vectorstore_artifacts_present_hub(
            provider=args.provider,
            model=effective_model,
            chunk_strategy=args.chunk_strategy,
            metodo_extracao=args.metodo_extracao,
            repo_id=args.repo_id,
        ):
            print(
                "  Vector store já existe no HuggingFace Hub; "
                "use --no-skip-existing para regerar."
            )
            return 0

    if args.output_dir is not None:
        output_dir = Path(args.output_dir)
        if args.skip_existing and vectorstore_artifacts_present(output_dir):
            print(
                f"  Vector store já existe em {output_dir}; "
                "use --no-skip-existing para regerar."
            )
            return 0
        return _run_with_output_dir(args, output_dir)

    return _run_in_memory(args)


def _gerar_vectorstore(args: argparse.Namespace):
    """Carrega chunks do Hub e constrói índice, metadata e manifest em memória."""
    df_chunks_corpus = carregar_chunks_hub(args.repo_id)
    df_chunks_filtrados = _filtrar_chunks(
        df_chunks_corpus,
        chunk_strategy=args.chunk_strategy,
        metodo_extracao=args.metodo_extracao,
        amostra=args.amostra,
    )
    print(
        f"  {len(df_chunks_filtrados)} chunks após filtro "
        f"(chunk_strategy={args.chunk_strategy}, "
        f"metodo_extracao={args.metodo_extracao})"
    )

    store, metadata, parents, manifest = construir_vectorstore(
        df_chunks_filtrados,
        df_chunks_corpus,
        provider=args.provider,
        model_name=args.model,
        chunk_strategy=args.chunk_strategy,
        metodo_extracao=args.metodo_extracao,
        batch_size=args.batch_size,
        corpus_repo=args.repo_id,
    )
    return store, metadata, parents, manifest


def _run_in_memory(args: argparse.Namespace) -> int:
    """Gera e, se solicitado, publica sem criar arquivos locais."""
    store, metadata, parents, manifest = _gerar_vectorstore(args)

    print("  Vector store gerada em memória; nenhum artefato local foi gravado.")
    _imprimir_resumo(store, metadata, parents, manifest)

    if args.publicar:
        publicar_vectorstore_memoria(
            store=store,
            metadata=metadata,
            parents=parents,
            manifest=manifest,
            provider=manifest["provider"],
            model=manifest["model"],
            chunk_strategy=args.chunk_strategy,
            metodo_extracao=args.metodo_extracao,
            repo_id=args.repo_id,
        )

    return 0


def _run_with_output_dir(args: argparse.Namespace, output_dir: Path) -> int:
    """Gera a vector store e grava em diretório local explícito para debug."""
    store, metadata, parents, manifest = _gerar_vectorstore(args)

    persistir_vectorstore(
        output_dir,
        store=store,
        metadata=metadata,
        parents=parents,
        manifest=manifest,
    )
    print(f"  Vector store salva em {output_dir}")
    _imprimir_resumo(store, metadata, parents, manifest)

    if args.publicar:
        publicar_vectorstore(
            output_dir,
            provider=manifest["provider"],
            model=manifest["model"],
            chunk_strategy=args.chunk_strategy,
            metodo_extracao=args.metodo_extracao,
            repo_id=args.repo_id,
        )

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gera e publica uma vector store FAISS sobre chunks do Hub."
        )
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
        help="Modelo OpenAI de embeddings (ignorado para provider=hash).",
    )
    parser.add_argument(
        "--chunk-strategy",
        choices=CHUNK_STRATEGIES,
        required=True,
        help="Estratégia de chunks a indexar.",
    )
    parser.add_argument(
        "--metodo-extracao",
        choices=METODOS_EXTRACAO,
        required=True,
        help="Formato de saída da Camada 1.",
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=None,
        help="Usa apenas os primeiros N chunks após o filtro.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=EMBEDDING_BATCH_SIZE,
        help="Quantidade de chunks por chamada de embedding.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Diretório local de saída. Default: não grava arquivos locais. "
            "Use apenas para debug."
        ),
    )
    parser.add_argument(
        "--repo-id",
        default=HF_DATASET_REPO,
        help="Dataset do HuggingFace Hub com data/chunks/.",
    )
    parser.add_argument(
        "--publicar",
        action="store_true",
        help="Publica a vector store em data/vectorstores/ no Hub.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Pula a geração se a combinação já existe no Hub quando --publicar "
            "está ativo; com --output-dir, consulta o diretório local explícito."
        ),
    )

    args = parser.parse_args()
    _validar_batch_size(args.batch_size)
    return args


def _effective_model_name(provider: str, model: str) -> str:
    """Modelo usado para nomear artefatos locais antes de instanciar o embedder."""
    if provider == "hash":
        return "hash"
    return model


def _filtrar_chunks(
    df_chunks: pd.DataFrame,
    *,
    chunk_strategy: str,
    metodo_extracao: str,
    amostra: int | None,
) -> pd.DataFrame:
    filtered = df_chunks[
        (df_chunks["chunk_strategy"] == chunk_strategy)
        & (df_chunks["metodo_extracao"] == metodo_extracao)
    ].copy()
    if amostra is not None:
        if amostra <= 0:
            raise ValueError("--amostra deve ser maior que zero")
        filtered = filtered.head(amostra).copy()
    if filtered.empty:
        raise RuntimeError(
            "Filtro selecionado não retornou chunks. "
            "Verifique se a estratégia/metodo está publicada no Hub."
        )
    return filtered.reset_index(drop=True)


def _validar_chunks_para_indexacao(df_chunks: pd.DataFrame) -> None:
    obrigatorias = {
        "chunk_id",
        "texto",
        "chunk_strategy",
        "metodo_extracao",
        "tipo",
        "parent_chunk_id",
    }
    faltando = obrigatorias - set(df_chunks.columns)
    if faltando:
        raise RuntimeError(
            f"Chunks sem colunas obrigatórias: {sorted(faltando)}"
        )

    texto_vazio = df_chunks["texto"].fillna("").astype(str).str.strip().eq("")
    if texto_vazio.any():
        ids = df_chunks.loc[texto_vazio, "chunk_id"].tolist()[:10]
        raise RuntimeError(f"Chunks com texto vazio: {ids}")


def _validar_batch_size(batch_size: int) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    if batch_size > MAX_OPENAI_BATCH_ITEMS:
        raise ValueError(
            f"batch_size={batch_size} excede o limite de "
            f"{MAX_OPENAI_BATCH_ITEMS} itens por chamada."
        )


def _imprimir_resumo(
    store: FAISSVectorStore,
    metadata: pd.DataFrame,
    parents: pd.DataFrame | None,
    manifest: dict,
) -> None:
    print("\nResumo da vector store:")
    print(f"  ntotal: {store.ntotal}")
    print(f"  dimension: {store.dimension}")
    print(f"  parents: {0 if parents is None else len(parents)}")
    print("  manifest:")
    for key, value in sorted(manifest.items()):
        if key == "extra":
            continue
        print(f"    {key}: {value}")


if __name__ == "__main__":
    sys.exit(main())
