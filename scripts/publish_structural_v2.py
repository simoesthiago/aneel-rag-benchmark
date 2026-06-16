"""Publica chunks + vector stores v2 das estratégias estruturais no repo v2.

Gera os chunks com o parser/splitter corrigidos (markdown-aware + merge),
constrói as stores em memória (`large` e `small`) e publica tudo num dataset HF
de staging v2. `fixed-size` NÃO entra (não usa o splitter — segue do Marco B no
repo oficial).

Uso:
  # dry-run grátis (hash, sem publicar, amostra pequena) — valida o encanamento:
  python scripts/publish_structural_v2.py --provider hash --no-publish --amostra 40
  # run real (pago) — embeddings reais + publica no repo v2:
  python scripts/publish_structural_v2.py --provider openai

Reusa funções oficiais: `chunk_article_aware` / `chunk_parent_child` (chunking),
`construir_vectorstore` (build em memória), `publicar_vectorstore_memoria` e
`publicar_chunks` (upload ao Hub).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

STRATEGIES = ("article-aware", "hierarchical-child")
METODOS = ("texto", "markdown")
MODELS = ("text-embedding-3-large", "text-embedding-3-small")
DEFAULT_REPO = "simoesthiago/aneel-vectorstores-h12"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["hash", "openai"], default="hash",
        help="hash = dry-run grátis offline; openai = embeddings reais (pago).",
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument(
        "--no-publish", action="store_true",
        help="Constrói tudo mas não sobe ao Hub (dry-run de encanamento).",
    )
    parser.add_argument(
        "--amostra", type=int, default=None,
        help="Usa só os primeiros N documentos por método (acelera o dry-run).",
    )
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    os.environ["EMBEDDING_PROVIDER"] = args.provider

    from huggingface_hub import HfApi, create_repo  # noqa: E402

    from src.chunking.article_aware import chunk_article_aware  # noqa: E402
    from src.chunking.hierarchical import chunk_parent_child  # noqa: E402
    from src.chunking.run import publicar_chunks  # noqa: E402
    from src.config.settings import HF_DATASET_REPO  # noqa: E402
    from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402
    from src.vectorstore.faiss_store import INDEX_FILENAME  # noqa: E402
    from src.vectorstore.hub import (  # noqa: E402
        hub_prefix,
        publicar_vectorstore_memoria,
    )
    from src.vectorstore.manifest import MANIFEST_FILENAME  # noqa: E402
    from src.vectorstore.metadata import (  # noqa: E402
        METADATA_FILENAME,
        PARENTS_FILENAME,
    )
    from src.vectorstore.run import construir_vectorstore  # noqa: E402

    print(f"== Publish estrutural v2 | provider={args.provider} "
          f"| publish={not args.no_publish} | repo={args.repo_id} ==")
    if args.provider == "openai":
        print("  ATENÇÃO: embeddings reais (PAGO).")

    corpus = carregar_corpus_hub()

    # Resume: lista os arquivos já no repo v2 uma vez, para pular stores prontas
    # (o ambiente mata runs longos; sem isso, re-rodar re-pagaria os embeddings).
    if not args.no_publish:
        create_repo(
            repo_id=args.repo_id, repo_type="dataset", private=True,
            exist_ok=True,
        )
    existentes: set[str] = set()
    if not args.no_publish:
        existentes = set(
            HfApi().list_repo_files(args.repo_id, repo_type="dataset")
        )

    def store_presente(strategy: str, metodo: str, model: str) -> bool:
        prefix = hub_prefix(
            provider="openai", model=model, chunk_strategy=strategy,
            metodo_extracao=metodo,
        )
        req = {
            f"{prefix}/{INDEX_FILENAME}",
            f"{prefix}/{METADATA_FILENAME}",
            f"{prefix}/{MANIFEST_FILENAME}",
        }
        if strategy == "hierarchical-child":
            req.add(f"{prefix}/{PARENTS_FILENAME}")
        return req.issubset(existentes)

    # Gera chunks sob demanda (1 vez por estratégia/método; barato). Só geramos
    # quando algo daquele par precisa ser construído ou publicado.
    chunk_cache: dict[tuple[str, str], tuple[pd.DataFrame, pd.DataFrame]] = {}

    def get_chunks(
        strategy: str, metodo: str
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        key = (strategy, metodo)
        if key not in chunk_cache:
            docs = corpus[corpus["metodo_extracao"].astype(str) == metodo]
            if args.amostra is not None:
                docs = docs.head(args.amostra)
            records = docs.to_dict("records")
            if strategy == "article-aware":
                df = pd.DataFrame(
                    [c for d in records for c in chunk_article_aware(d)]
                )
                chunk_cache[key] = (df, df)
            else:
                df_hier = pd.DataFrame(
                    [c for d in records for c in chunk_parent_child(d)]
                )
                df_children = df_hier[
                    df_hier["chunk_strategy"] == "hierarchical-child"
                ].copy()
                chunk_cache[key] = (df_children, df_hier)
            print(f"  chunks {strategy}|{metodo}: {len(chunk_cache[key][0])}")
        return chunk_cache[key]

    # Constrói e publica as stores: 2 estratégias × 2 métodos × 2 modelos.
    combos = [(s, mt) for s in STRATEGIES for mt in METODOS]
    for strategy, metodo in combos:
        for model in MODELS:
            if not args.no_publish and store_presente(strategy, metodo, model):
                print(f"  skip (já publicado): {strategy}|{metodo}|{model}")
                continue
            df_filt, df_corpus = get_chunks(strategy, metodo)
            print(f"\n-- build {strategy} | {metodo} | {model} --")
            store, metadata, parents, manifest = construir_vectorstore(
                df_filt, df_corpus,
                provider=args.provider, model_name=model,
                chunk_strategy=strategy, metodo_extracao=metodo,
                batch_size=args.batch_size, corpus_repo=HF_DATASET_REPO,
            )
            if not args.no_publish:
                prefix = publicar_vectorstore_memoria(
                    store=store, metadata=metadata, manifest=manifest,
                    parents=parents, provider=args.provider, model=model,
                    chunk_strategy=strategy, metodo_extracao=metodo,
                    repo_id=args.repo_id,
                )
                print(f"   publicado: {args.repo_id}/{prefix}")

    # Publica os chunks v2 (uma vez), se ainda não estiverem no repo.
    if not args.no_publish:
        if any(f.startswith("data/chunks/") for f in existentes):
            print("\n  chunks v2 já publicados — pulando.")
        else:
            partes = []
            for metodo in METODOS:
                partes.append(get_chunks("article-aware", metodo)[0])
                partes.append(get_chunks("hierarchical-child", metodo)[1])
            df_all = pd.concat(partes, ignore_index=True)
            print(f"\n-- publicando {len(df_all)} chunks v2 em {args.repo_id} --")
            publicar_chunks(df_all, repo_id=args.repo_id)

    print("\nConcluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
