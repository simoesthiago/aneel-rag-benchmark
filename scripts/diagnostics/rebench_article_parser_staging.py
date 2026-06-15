"""Rebench escopado do parser `article-aware` corrigido (H12) — em memória.

Pergunta que este script responde: **o parser corrigido (que parou de
fragmentar referências cruzadas a `Art. N`) faz `article-aware` e
`hierarchical-child` recuperarem melhor**, ou a vitória do `fixed-size` foi
robustez de verdade?

Como ele responde, do princípio:
  1. Lê o corpus do Hub (só `texto`) e gera chunks com o parser NOVO em
     processo — nada de chunks publicados.
  2. Monta a vector store (embeddings + FAISS + metadata/parents/manifest)
     INTEIRAMENTE na RAM, reusando `construir_vectorstore` (a mesma função de
     produção). Nada é gravado em disco.
  3. Pontua com `run_config` (retriever + métricas OFICIAIS) lendo a store da
     RAM via `bundle`, então o número é comparável com a matriz do Marco B.
  4. Compara `recall/doc_recall/nDCG` contra os números "antes" do Marco B e
     aplica a régua pré-comprometida (ver `PROGRESS.md`).

Custo e artefatos:
  - `--provider hash` (DEFAULT): embeddings falsos, OFFLINE, grátis. Só valida
    que o encanamento roda ponta a ponta. Os números NÃO têm significado.
  - `--provider openai`: embeddings reais (pago, ~US$ 1–3). É o que decide.
  - `--publish`: além de pontuar, sobe a store da RAM para `--staging-repo`
    (para promoção futura sem recomputar). Sem `--publish`, nada vai pro Hub.
  - Único artefato em disco: o relatório de KB em
    `data/evaluation/results/diagnostic/rebench_article_parser.{md,json}`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

# Números "antes" da matriz oficial do Marco B (large·texto·sem-rerank, com
# higiene), copiados de data/evaluation/report/tables/retrieval_matrix.md.
# São o baseline contra o qual medimos o efeito do parser corrigido.
BASELINE_MARCO_B: dict[tuple[str, str], dict[str, float]] = {
    ("article-aware", "flat"): {
        "recall_at_k": 0.625,
        "doc_recall_at_k": 0.833,
        "ndcg_at_k": 0.465,
    },
    ("hierarchical-child", "flat"): {
        "recall_at_k": 0.542,
        "doc_recall_at_k": 0.812,
        "ndcg_at_k": 0.401,
    },
    ("hierarchical-child", "hierarchical"): {
        "recall_at_k": 0.583,
        "doc_recall_at_k": 0.812,
        "ndcg_at_k": 0.459,
    },
}
# Alvo a alcançar: fixed-size·texto·flat·sem-rerank (mesma tabela).
FIXED_SIZE_TARGET = {"recall_at_k": 0.896, "doc_recall_at_k": 0.938}
# Régua pré-comprometida: article-aware·texto precisa fechar a maior parte da
# lacuna até o fixed-size. Limiar fixado ANTES de medir.
RECALL_PROMOTE_THRESHOLD = 0.80

OUT_JSON = Path(
    "data/evaluation/results/diagnostic/rebench_article_parser.json"
)
OUT_MD = Path("data/evaluation/results/diagnostic/rebench_article_parser.md")

DEFAULT_STAGING_REPO = "simoesthiago/aneel-vectorstores-h12-staging"
METODO = "texto"  # escopo: só texto (o parser quase não move markdown).


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["hash", "openai"],
        default="hash",
        help="hash = dry-run grátis offline; openai = run real pago.",
    )
    parser.add_argument(
        "--model",
        default="text-embedding-3-large",
        help="Modelo de embedding (só vale para --provider openai).",
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=None,
        help="Usa só os primeiros N documentos (acelera o dry-run).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Sobe as stores da RAM para --staging-repo (habilita promoção).",
    )
    parser.add_argument(
        "--staging-repo",
        default=DEFAULT_STAGING_REPO,
        help="Dataset HF de staging para publicar (só com --publish).",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # Garante que o embedder de query (usado pelo retriever na pontuação) use o
    # MESMO provider do build — senão um dry-run hash dispararia OpenAI pago.
    os.environ["EMBEDDING_PROVIDER"] = args.provider

    # Imports tardios: depois de fixar EMBEDDING_PROVIDER no ambiente.
    from src.config.settings import GROUND_TRUTH_VERSION  # noqa: E402
    from src.embeddings.embedder import build_embedder  # noqa: E402
    from src.evaluation.benchmark import StoreConfig, run_config  # noqa: E402
    from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
    from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402
    from src.rag.retriever import Retriever  # noqa: E402

    # Embedder único (hash ou openai), reusado para query em toda config.
    embedder = build_embedder(provider=args.provider, model_name=args.model)

    print(f"== Rebench article-aware (H12) | provider={args.provider} ==")
    if args.provider == "openai":
        print("  ATENÇÃO: este run gera embeddings reais (PAGO).")

    corpus = _load_corpus_texto(carregar_corpus_hub, amostra=args.amostra)
    print(f"  Corpus texto: {len(corpus)} documentos")

    # 1+2: gera chunks com o parser novo e monta as stores na RAM.
    bundles = _build_bundles(
        corpus,
        provider=args.provider,
        model=args.model,
        batch_size=args.batch_size,
    )

    # 3: pontua lendo a store da RAM (bundle), com retriever+métricas oficiais.
    questions = load_ground_truth_hub()
    print(
        f"  GT {GROUND_TRUTH_VERSION}: {len(questions)} perguntas | "
        f"top_k={args.top_k}"
    )
    configs = _target_configs(StoreConfig, args.model)

    results: list[dict[str, Any]] = []
    for config in configs:
        bundle = bundles[(config.chunk_strategy, METODO)]

        def factory(cfg, repo_id, query_cache=None, _bundle=bundle):
            # Constrói o Retriever direto com a store da RAM e o embedder do
            # provider escolhido (o factory padrão forçaria OpenAI pelo
            # manifest, quebrando o dry-run hash). rerank=False nestas configs.
            exclude_situacoes = (
                frozenset({"revogada"}) if cfg.exclude_revogadas else None
            )
            return Retriever(
                provider=cfg.provider,
                model=cfg.model,
                chunk_strategy=cfg.chunk_strategy,
                metodo_extracao=cfg.metodo_extracao,
                mode=cfg.mode,
                repo_id=repo_id,
                bundle=_bundle,
                query_cache=query_cache,
                embedder=embedder,
                candidates_k=cfg.candidates_k_override,
                exclude_situacoes=exclude_situacoes,
                exclude_superseded_versions=cfg.exclude_superseded_versions,
                restrict_to_query_submodulo=cfg.restrict_to_query_submodulo,
                boost_identificador=cfg.boost_identificador,
            )

        summary = run_config(
            config,
            questions,
            top_k=args.top_k,
            repo_id=None,
            retriever_factory=factory,
        )
        results.append(_score_row(config, summary))
        depois = results[-1]["depois"]
        print(
            f"  {config.chunk_strategy}|{config.mode}: "
            f"recall {depois['recall_at_k']:.3f} "
            f"doc_recall {depois['doc_recall_at_k']:.3f} "
            f"nDCG {depois['ndcg_at_k']:.3f}"
        )

    # Grava o relatório ANTES de publicar: o número (que pagamos) nunca pode
    # se perder por uma falha no upload ao Hub.
    verdict = _verdict(results, provider=args.provider)
    payload = {
        "provider": args.provider,
        "model": args.model,
        "metodo_extracao": METODO,
        "ground_truth_version": GROUND_TRUTH_VERSION,
        "top_k": args.top_k,
        "amostra": args.amostra,
        "published_to": None,
        "fixed_size_target": FIXED_SIZE_TARGET,
        "recall_promote_threshold": RECALL_PROMOTE_THRESHOLD,
        "results": results,
        "verdict": verdict,
    }
    _write_report(payload)
    print(f"\nVeredito: {verdict}")

    # Publica no staging só se pedido (promoção futura sem recomputar). Falha
    # de upload é não-fatal: o relatório com o veredito já está salvo.
    if args.publish:
        try:
            payload["published_to"] = _publish_bundles(
                bundles, provider=args.provider, model=args.model,
                staging_repo=args.staging_repo,
            )
            _write_report(payload)  # regrava com o destino publicado
        except Exception as exc:  # noqa: BLE001
            print(f"  AVISO: publish no staging falhou (não-fatal): {exc}")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")
    return 0


def _write_report(payload: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    OUT_MD.write_text(_render_markdown(payload), encoding="utf-8")


def _load_corpus_texto(loader, *, amostra: int | None) -> pd.DataFrame:
    df = loader()
    df = df[df["metodo_extracao"].astype(str) == METODO].copy()
    df = df.reset_index(drop=True)
    if amostra is not None:
        df = df.head(amostra).copy()
    return df


def _build_bundles(
    corpus: pd.DataFrame,
    *,
    provider: str,
    model: str,
    batch_size: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Gera chunks (parser novo) e monta cada store na RAM. Devolve bundles."""
    from src.chunking.article_aware import chunk_article_aware
    from src.chunking.hierarchical import chunk_parent_child
    from src.vectorstore.run import construir_vectorstore

    records_article: list[dict[str, Any]] = []
    records_hier: list[dict[str, Any]] = []
    for document in corpus.to_dict("records"):
        records_article.extend(chunk_article_aware(document))
        records_hier.extend(chunk_parent_child(document))

    df_article = pd.DataFrame(records_article)
    df_hier = pd.DataFrame(records_hier)
    df_children = df_hier[
        df_hier["chunk_strategy"] == "hierarchical-child"
    ].copy()

    bundles: dict[tuple[str, str], dict[str, Any]] = {}

    print(f"  Build article-aware: {len(df_article)} chunks ...")
    store_a, meta_a, _, manifest_a = construir_vectorstore(
        df_article,
        df_article,
        provider=provider,
        model_name=model,
        chunk_strategy="article-aware",
        metodo_extracao=METODO,
        batch_size=batch_size,
        corpus_repo="ram-prototype",
    )
    bundles[("article-aware", METODO)] = {
        "index": store_a, "metadata": meta_a, "parents": None,
        "manifest": manifest_a, "dir": None,
    }

    print(f"  Build hierarchical-child: {len(df_children)} chunks ...")
    store_h, meta_h, parents_h, manifest_h = construir_vectorstore(
        df_children,
        df_hier,
        provider=provider,
        model_name=model,
        chunk_strategy="hierarchical-child",
        metodo_extracao=METODO,
        batch_size=batch_size,
        corpus_repo="ram-prototype",
    )
    bundles[("hierarchical-child", METODO)] = {
        "index": store_h, "metadata": meta_h, "parents": parents_h,
        "manifest": manifest_h, "dir": None,
    }
    return bundles


def _target_configs(StoreConfig, model: str) -> list[Any]:
    """As 3 linhas do Marco B que mudam com o parser, com higiene ligada."""
    base = [
        StoreConfig(
            provider="openai", model=model,
            chunk_strategy="article-aware", metodo_extracao=METODO,
            mode="flat",
        ),
        StoreConfig(
            provider="openai", model=model,
            chunk_strategy="hierarchical-child", metodo_extracao=METODO,
            mode="flat",
        ),
        StoreConfig(
            provider="openai", model=model,
            chunk_strategy="hierarchical-child", metodo_extracao=METODO,
            mode="hierarchical",
        ),
    ]
    # Higiene ligada para bater com a matriz do Marco B (que a aplicou).
    return [
        replace(
            c,
            exclude_revogadas=True,
            exclude_superseded_versions=True,
            restrict_to_query_submodulo=True,
        )
        for c in base
    ]


def _score_row(config, summary: dict[str, Any]) -> dict[str, Any]:
    key = (config.chunk_strategy, config.mode)
    antes = BASELINE_MARCO_B[key]
    depois = {
        "recall_at_k": round(summary["recall_at_k"], 4),
        "doc_recall_at_k": round(summary["doc_recall_at_k"], 4),
        "ndcg_at_k": round(summary["ndcg_at_k"], 4),
    }
    return {
        "chunk_strategy": config.chunk_strategy,
        "mode": config.mode,
        "antes": antes,
        "depois": depois,
        "delta_recall": round(depois["recall_at_k"] - antes["recall_at_k"], 4),
    }


def _publish_bundles(
    bundles, *, provider: str, model: str, staging_repo: str
) -> dict[str, str]:
    from huggingface_hub import create_repo

    from src.vectorstore.hub import publicar_vectorstore_memoria

    # `publicar_vectorstore_memoria` faz commit assumindo repo existente; cria
    # o dataset de staging (privado) se ainda não existir.
    create_repo(
        repo_id=staging_repo, repo_type="dataset", private=True, exist_ok=True
    )

    published: dict[str, str] = {}
    for (strategy, metodo), bundle in bundles.items():
        prefix = publicar_vectorstore_memoria(
            store=bundle["index"],
            metadata=bundle["metadata"],
            manifest=bundle["manifest"],
            parents=bundle["parents"],
            provider=provider,
            model=model,
            chunk_strategy=strategy,
            metodo_extracao=metodo,
            repo_id=staging_repo,
        )
        published[f"{strategy}|{metodo}"] = f"{staging_repo}/{prefix}"
        print(f"  publicado: {staging_repo}/{prefix}")
    return published


def _verdict(results: list[dict[str, Any]], *, provider: str) -> str:
    if provider != "openai":
        return (
            "DRY-RUN (provider=hash): encanamento validado, mas os números NÃO "
            "têm significado. Rode com --provider openai para o veredito real."
        )
    article = next(
        (r for r in results if r["chunk_strategy"] == "article-aware"), None
    )
    if article is None:
        return "INDEFINIDO: article-aware não medido."
    recall = article["depois"]["recall_at_k"]
    if recall >= RECALL_PROMOTE_THRESHOLD:
        return (
            f"PROMOVER: article-aware·texto recall {recall:.3f} >= "
            f"{RECALL_PROMOTE_THRESHOLD} — o parser corrigido fecha a lacuna "
            "até fixed-size. Justifica re-embedding oficial das estruturais."
        )
    return (
        f"NÃO PROMOVER: article-aware·texto recall {recall:.3f} < "
        f"{RECALL_PROMOTE_THRESHOLD} — o fix não fecha a lacuna. Documentar "
        "que fixed-size venceu por robustez; sem re-embedding oficial."
    )


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Rebench escopado — parser article-aware corrigido (H12)",
        "",
        f"- provider: `{payload['provider']}` | modelo: `{payload['model']}` "
        f"| método: `{payload['metodo_extracao']}`",
        f"- ground truth: `{payload['ground_truth_version']}` "
        f"| top_k: {payload['top_k']} | amostra: {payload['amostra']}",
        f"- alvo (fixed-size): recall {payload['fixed_size_target']['recall_at_k']} "
        f"/ doc_recall {payload['fixed_size_target']['doc_recall_at_k']}",
        f"- régua de promoção: article-aware recall >= "
        f"{payload['recall_promote_threshold']}",
    ]
    if payload["published_to"]:
        lines.append(f"- publicado em staging: `{payload['published_to']}`")
    lines += [
        "",
        f"**Veredito: {payload['verdict']}**",
        "",
        "| strategy | mode | recall antes | recall depois | Δ recall | "
        "doc_recall antes | doc_recall depois | nDCG antes | nDCG depois |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in payload["results"]:
        a, d = r["antes"], r["depois"]
        lines.append(
            f"| {r['chunk_strategy']} | {r['mode']} | "
            f"{a['recall_at_k']:.3f} | {d['recall_at_k']:.3f} | "
            f"{r['delta_recall']:+.3f} | "
            f"{a['doc_recall_at_k']:.3f} | {d['doc_recall_at_k']:.3f} | "
            f"{a['ndcg_at_k']:.3f} | {d['ndcg_at_k']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
