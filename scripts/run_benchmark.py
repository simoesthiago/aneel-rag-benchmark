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
    build_rag_failure_analysis,
    build_rag_baseline_configs,
    build_rag_rerank_pairing,
    build_store_configs,
    load_benchmark_result_from_per_question_json,
    render_rag_rerank_pairing_md,
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
    parser.add_argument(
        "--from-cache",
        type=Path,
        default=None,
        help=(
            "Caminho para um per_question.json já gerado. Quando definido, "
            "pula a chamada ao LLM/retriever e regenera apenas os artefatos "
            "derivados (failure_analysis, rerank_pairing) a partir do JSON. "
            "Só faz sentido com --mode rag."
        ),
    )
    parser.add_argument(
        "--query-expansion",
        action="store_true",
        help=(
            "Em --mode rag, adiciona configs com rewriter LLM antes do "
            "retrieval. Resulta em 4 configs ao invés de 2 (cartesiano "
            "rerank × QE), permitindo medir a interação. Exige LLM_API_KEY "
            "ou OPENAI_API_KEY."
        ),
    )
    parser.add_argument(
        "--query-expansion-model",
        type=str,
        default=None,
        help=(
            "Modelo OpenAI usado pelo rewriter de query expansion. "
            "Default = LLM_MODEL (settings)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from_cache: Path | None = args.from_cache
    if from_cache is not None:
        if args.mode != "rag":
            raise SystemExit(
                "--from-cache só faz sentido com --mode rag (os artefatos "
                "derivados pareados são exclusivos do RAG)."
            )
        print(f"Carregando per_question.json em cache: {from_cache}")
        result = load_benchmark_result_from_per_question_json(from_cache)
        print(
            f"  {len(result.metrics)} configs reconstruídas a partir do "
            "JSON (sem chamada LLM)."
        )
    else:
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
            configs = build_rag_baseline_configs(
                query_expansion=args.query_expansion,
            )
            if args.rerank:
                print(
                    "  Aviso: --mode rag já inclui baseline sem rerank e com "
                    "rerank; --rerank foi ignorado."
                )
            if args.query_expansion_model and not args.query_expansion:
                print(
                    "  Aviso: --query-expansion-model só tem efeito com "
                    "--query-expansion."
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

        if query_cache is not None and args.cache_path is not None:
            query_cache.save()
            print(f"  Cache persistido: {args.cache_path}")

    df = result.metrics

    output_dir: Path = args.output_dir or Path(
        "data/evaluation/results/rag-50"
        if args.mode == "rag"
        else "data/evaluation/results/retrieval-50"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if from_cache is None:
        aggregate = df.drop(columns=["per_question"])
        for column in (
            "llm_status_counts",
            "generator_status_counts",
            "failure_type_counts",
        ):
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
                    "query_expansion": bool(row.get("query_expansion") or False),
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
    else:
        aggregate = None
        print(
            "  --from-cache ativo: results.csv e per_question.json não são "
            "regravados (o JSON de entrada é a fonte da verdade)."
        )

    if args.mode == "rag":
        analysis = build_rag_failure_analysis(result)
        analysis_path = output_dir / "failure_analysis.json"
        analysis_path.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path = output_dir / "failure_analysis.md"
        markdown_path.write_text(
            _render_rag_failure_analysis_markdown(analysis),
            encoding="utf-8",
        )
        print(f"  Diagnóstico de falhas salvo: {analysis_path}")
        print(f"  Diagnóstico legível salvo: {markdown_path}")

        rerank_flags = {bool(r["rerank"]) for _, r in df.iterrows()}
        qe_flags = {
            bool(r.get("query_expansion") or False) for _, r in df.iterrows()
        }
        # Pareamento rerank: só roda quando há exatamente 2 configs
        # diferindo apenas em rerank. Com query_expansion ativo, são 4
        # configs e o rerank pairing é pulado em favor do QE pairing
        # (que considera as 4 combinações).
        if rerank_flags == {True, False} and qe_flags == {False}:
            pairing = build_rag_rerank_pairing(result)
            pairing_json = output_dir / "rerank_pairing.json"
            pairing_json.write_text(
                json.dumps(pairing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            pairing_md = output_dir / "rerank_pairing.md"
            pairing_md.write_text(
                render_rag_rerank_pairing_md(pairing),
                encoding="utf-8",
            )
            print(f"  Pareamento rerank salvo: {pairing_json}")
            print(f"  Pareamento legível salvo: {pairing_md}")
        elif qe_flags == {True, False}:
            print(
                "  Pareamento rerank pulado (4 configs com QE); o pareamento "
                "QE cobre rerank × query_expansion."
            )
        else:
            print(
                "  Pareamento rerank ignorado: precisa de ambas configs "
                f"rerank=False/True; recebido {sorted(rerank_flags)}."
            )

        # Pareamento QE: ativado quando há configs com e sem query_expansion.
        if qe_flags == {True, False}:
            from scripts.analyze_query_expansion_pairing import (
                _config_by_flags,
                build_qe_pairing,
                render_qe_pairing_md,
            )

            qe_payload = json.loads(detail_path.read_text(encoding="utf-8"))
            par1 = build_qe_pairing(
                _config_by_flags(qe_payload, rerank=False, qe=False),
                _config_by_flags(qe_payload, rerank=False, qe=True),
            )
            par2 = build_qe_pairing(
                _config_by_flags(qe_payload, rerank=True, qe=False),
                _config_by_flags(qe_payload, rerank=True, qe=True),
            )
            qe_pairing_json = output_dir / "query_expansion_pairing.json"
            qe_pairing_json.write_text(
                json.dumps(
                    {"par1_baseline": par1, "par2_with_rerank": par2},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            qe_pairing_md = output_dir / "query_expansion_pairing.md"
            qe_pairing_md.write_text(
                render_qe_pairing_md(par1, par2), encoding="utf-8"
            )
            print(f"  Pareamento QE salvo: {qe_pairing_json}")
            print(f"  Pareamento QE legível: {qe_pairing_md}")
            print(
                f"    Par 1 (sem rerank): {par1['decision_rule']['verdict']} "
                f"saved={par1['summary']['saved_count']} broken={par1['summary']['broken_count']}"
            )
            print(
                f"    Par 2 (com rerank): {par2['decision_rule']['verdict']} "
                f"saved={par2['summary']['saved_count']} broken={par2['summary']['broken_count']}"
            )

    if aggregate is not None and "ndcg_at_k" in aggregate.columns:
        print("\nResumo (top-5 por nDCG@k):")
        top = aggregate.sort_values("ndcg_at_k", ascending=False).head(5)
        pd.set_option("display.max_columns", None)
        print(top.to_string(index=False))


def _render_rag_failure_analysis_markdown(analysis: dict) -> str:
    lines = [
        "# Diagnóstico de usabilidade RAG",
        "",
        "## Definição",
        "",
        (
            "`answer_usable = recall_at_k > 0 and citation_accuracy >= 0.5 and "
            "answer_correctness >= 0.8`."
        ),
        "",
        "Essa métrica separa resposta fiel ao contexto errado de resposta "
        "realmente útil para o usuário final.",
        "",
    ]
    for config in analysis.get("configs", []):
        lines.extend(
            [
                f"## {config.get('label')}",
                "",
                f"- `answer_usable_rate`: {config.get('answer_usable_rate')}",
                f"- `num_failures`: {config.get('num_failures')}",
                f"- `failure_type_counts`: {config.get('failure_type_counts')}",
                "",
            ]
        )
        failures = list(config.get("failures") or [])
        if not failures:
            lines.extend(["Nenhuma falha não-usável nesta configuração.", ""])
            continue
        lines.extend(
            [
                "| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |",
                "|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for failure in failures:
            lines.append(
                "| {question_id} | {failure_type} | {next_focus} | "
                "{recall_at_k} | {doc_recall_at_k} | {citation_accuracy} | "
                "{answer_correctness} |".format(**failure)
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
