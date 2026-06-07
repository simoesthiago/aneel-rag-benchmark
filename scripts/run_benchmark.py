"""CLI dos benchmarks de retrieval e RAG (Camada 3 -> Camada 4).

Carrega o ground truth `retrieval-50` do HuggingFace Hub (ou de um arquivo
local). Em `--mode retrieval`, roda a matriz de retrievers publicada. Em
`--mode rag`, roda o smoke ponta-a-ponta com geração, citações e juiz LLM
opcional. Salva a tabela final em CSV e um JSON detalhado por pergunta.

Uso:

    python3 scripts/run_benchmark.py --top-k 10
    python3 scripts/run_benchmark.py --mode rag --limit 5
    python3 scripts/run_benchmark.py --ground-truth <arquivo.jsonl>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permite rodar como `python scripts/run_benchmark.py` na raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import (  # noqa: E402
    build_rag_baseline_configs,
    build_store_configs,
    run_full_benchmark,
    run_rag_benchmark,
)
from src.evaluation.ground_truth import (  # noqa: E402
    load_ground_truth_hub,
    load_ground_truth_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=("retrieval", "rag"),
        default="retrieval",
        help=(
            "Modo do benchmark. `retrieval` avalia apenas busca; `rag` roda "
            "retrieve -> geração -> juiz LLM nas configs do smoke RAG."
        ),
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help=(
            "Caminho local para o JSONL do ground truth. Se omitido, baixa "
            "a versão publicada (retrieval-50) do HuggingFace Hub."
        ),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top-k usado em cada retrieve (default: 10).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Diretório de saída para o CSV agregado e JSON detalhado. "
            "Default: retrieval-50 para --mode retrieval; rag-50 para --mode rag."
        ),
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default=None,
        help="Repo HuggingFace alternativo (default: HF_DATASET_REPO).",
    )
    parser.add_argument(
        "--limit-configs",
        type=int,
        default=None,
        help=(
            "Quando definido, roda apenas as N primeiras configurações da "
            "matriz. Útil para smoke tests."
        ),
    )
    parser.add_argument(
        "--limit-questions",
        "--limit",
        type=int,
        default=None,
        dest="limit_questions",
        help="Quando definido, roda apenas as N primeiras perguntas do GT.",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help=(
            "Caminho opcional para persistir embeddings de query. "
            "Se omitido, o cache fica apenas em memória durante o run."
        ),
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help=(
            "Threads em paralelo (cada uma carrega 1 store inteira em "
            "memória — FAISS + metadata.parquet). Default 1 é seguro em "
            "máquina modesta; suba só se tiver RAM sobrando."
        ),
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help=(
            "Adiciona variantes +rerank (Cohere Rerank 3) à matriz. "
            "Dobra o número de configurações e exige COHERE_API_KEY."
        ),
    )
    parser.add_argument(
        "--rerank-candidates-k",
        type=int,
        default=None,
        help=(
            "Quando --rerank ativo, força o pool de candidatos densos antes "
            "do rerank (default do Retriever ≈ 50). Diagnóstico em "
            "data/evaluation/results/diagnostic/rerank_pool_comparison.md "
            "mostrou pool 100 sobe passage_recall +4 pp na melhor config, "
            "mas reduz doc_recall em -2 pp. Sem --rerank, é ignorado."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.ground_truth is not None:
        print(f"Carregando ground truth local: {args.ground_truth}")
        questions = load_ground_truth_jsonl(args.ground_truth)
    else:
        print("Baixando ground truth retrieval-50 do HuggingFace Hub ...")
        questions = load_ground_truth_hub()

    if args.limit_questions:
        questions = questions[: args.limit_questions]
    print(
        f"  {len(questions)} perguntas carregadas "
        "(somente corpus_supported entra nas métricas agregadas)."
    )

    if args.mode == "rag":
        configs = build_rag_baseline_configs()
        if args.rerank:
            print(
                "  Aviso: --mode rag já inclui baseline sem rerank e com "
                "rerank; --rerank foi ignorado."
            )
    else:
        configs = build_store_configs(
            include_rerank=args.rerank,
            rerank_candidates_k=args.rerank_candidates_k,
        )
    if args.limit_configs:
        configs = configs[: args.limit_configs]
    print(f"  {len(configs)} configurações a avaliar.")

    query_cache = (
        QueryEmbeddingCache(persist_path=args.cache_path)
        if args.cache_path is not None
        else None
    )

    if args.mode == "rag":
        result = run_rag_benchmark(
            questions,
            top_k=args.top_k,
            configs=configs,
            repo_id=args.repo_id,
            query_cache=query_cache,
        )
    else:
        result = run_full_benchmark(
            questions,
            top_k=args.top_k,
            configs=configs,
            repo_id=args.repo_id,
            query_cache=query_cache,
            max_workers=args.max_workers,
        )
    df = result.metrics

    if query_cache is not None and args.cache_path is not None:
        query_cache.save()
        print(f"  Cache persistido: {args.cache_path}")

    output_dir: Path = args.output_dir or Path(
        "data/evaluation/results/rag-50"
        if args.mode == "rag"
        else "data/evaluation/results/retrieval-50"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    aggregate = df.drop(columns=["per_question"])
    for column in ("llm_status_counts", "generator_status_counts"):
        if column in aggregate.columns:
            aggregate[column] = aggregate[column].map(
                lambda value: json.dumps(value, ensure_ascii=False)
            )
    csv_path = output_dir / "results.csv"
    aggregate.to_csv(csv_path, index=False)
    print(f"  Tabela agregada salva: {csv_path}")

    detalhe = []
    for _, row in df.iterrows():
        detalhe.append(
            {
                "model": row["model"],
                "chunk_strategy": row["chunk_strategy"],
                "metodo_extracao": row["metodo_extracao"],
                "mode": row["mode"],
                "rerank": bool(row["rerank"]),
                "llm_status_counts": row.get("llm_status_counts"),
                "generator_status_counts": row.get("generator_status_counts"),
                "per_question": row["per_question"],
            }
        )
    detail_path = output_dir / "per_question.json"
    detail_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "top_k": args.top_k,
                "skipped_questions": result.skipped_questions,
                "cache_stats": result.cache_stats,
                "results": detalhe,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  Detalhe por pergunta salvo: {detail_path}")

    print("\nResumo (top-5 por nDCG@k):")
    top = aggregate.sort_values("ndcg_at_k", ascending=False).head(5)
    pd.set_option("display.max_columns", None)
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
