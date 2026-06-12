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

from src.config import settings  # noqa: E402
from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.run_manifest import (  # noqa: E402
    build_run_manifest,
    default_run_dir,
    make_run_id,
    write_run_manifest,
)
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
        "--apply-hygiene",
        action="store_true",
        help=(
            "Em --mode retrieval, liga os filtros de higiene "
            "(sem_revogadas + sem_versoes_antigas + submodulo_exato) em todas "
            "as configs da matriz, deixando-a comparável ao pipeline RAG "
            "promovido (Fases F1/F1.5). Obrigatório nos runs oficiais do "
            "Marco B. Sem efeito em --mode rag (lá a higiene já é default)."
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
    parser.add_argument(
        "--rerank-pool-comparison",
        action="store_true",
        help=(
            "Em --mode rag, gera 3 configs (baseline + rerank@50 + "
            "rerank@100) para isolar o efeito do pool de candidatos densos "
            "do rerank (Fase 2 do roadmap). Exige COHERE_API_KEY. Emite "
            "rerank_pool_pairing.{json,md}. Incompatível com "
            "--query-expansion."
        ),
    )
    parser.add_argument(
        "--exclude-revogadas-comparison",
        action="store_true",
        help=(
            "Em --mode rag, gera 2 configs rerank@100 diferindo apenas no "
            "filtro de normas revogadas (Fase 1 do roadmap). Emite "
            "revogadas_pairing.{json,md}. Incompatível com --query-expansion "
            "e --rerank-pool-comparison."
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
            gt_source = f"local:{args.ground_truth}"
            gt_version = args.ground_truth.name
        else:
            print("Baixando ground truth retrieval-50 do HuggingFace Hub ...")
            questions = load_ground_truth_hub()
            gt_source = "hub"
            gt_version = settings.GROUND_TRUTH_VERSION

        if args.limit_questions:
            questions = questions[: args.limit_questions]
        print(
            f"  {len(questions)} perguntas carregadas "
            "(somente corpus_supported entra nas métricas agregadas)."
        )

        if args.mode == "rag":
            _modos_exp = [
                args.query_expansion,
                args.rerank_pool_comparison,
                args.exclude_revogadas_comparison,
            ]
            if sum(bool(m) for m in _modos_exp) > 1:
                raise SystemExit(
                    "--query-expansion, --rerank-pool-comparison e "
                    "--exclude-revogadas-comparison são mutuamente "
                    "exclusivos (escopos experimentais distintos)."
                )
            if args.rerank_pool_comparison:
                configs = build_rag_baseline_configs(rerank_pools=(50, 100))
            elif args.exclude_revogadas_comparison:
                configs = build_rag_baseline_configs(
                    exclude_revogadas_comparison=True,
                )
            else:
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
                apply_hygiene=args.apply_hygiene,
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

    # Novo contrato de `data/` (Marco A): runs brutos vão para
    # `data/evaluation/runs/<mode>/<run_id>/`, cada um com seu manifest.json.
    # `--output-dir` continua sobrescrevendo (usado por experimentos pareados).
    # Com `--from-cache` e sem override, os artefatos derivados ficam ao lado
    # do per_question.json de origem, não num run novo vazio.
    run_id = make_run_id()
    if args.output_dir is not None:
        output_dir = args.output_dir
    elif from_cache is not None:
        output_dir = from_cache.parent
    else:
        output_dir = default_run_dir(args.mode, run_id)
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
                    "candidates_k": (
                        int(row["candidates_k"])
                        if row.get("candidates_k") is not None
                        and not pd.isna(row.get("candidates_k"))
                        else None
                    ),
                    "query_expansion": bool(row.get("query_expansion") or False),
                    "exclude_revogadas": bool(
                        row.get("exclude_revogadas") or False
                    ),
                    "exclude_superseded_versions": bool(
                        row.get("exclude_superseded_versions") or False
                    ),
                    "restrict_to_query_submodulo": bool(
                        row.get("restrict_to_query_submodulo") or False
                    ),
                    "boost_identificador": bool(
                        row.get("boost_identificador") or False
                    ),
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
        # No modo cache, o próprio JSON de entrada é a fonte dos pareamentos
        # derivados (que leem `detail_path` adiante). Sem isto, os analyzers
        # disparavam UnboundLocalError.
        detail_path = from_cache
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
        revogadas_flags = {
            bool(r.get("exclude_revogadas") or False) for _, r in df.iterrows()
        }
        rerank_rows = [r for _, r in df.iterrows() if bool(r["rerank"])]
        rerank_pools = {r.get("candidates_k") for r in rerank_rows}
        # Modo pool-comparison: >= 2 configs rerank com pools distintos.
        # Detectado pela forma das configs (funciona também com --from-cache).
        pool_comparison = len(rerank_rows) >= 2 and len(rerank_pools) >= 2
        # Modo revogadas-comparison: 2 configs diferindo APENAS em
        # exclude_revogadas (mesmo rerank, mesmo pool). Após a Fase 1, o
        # rerank default já liga o filtro, então um run comum
        # [baseline, rerank+filtro] difere também em rerank — esse NÃO é o
        # pareamento de revogadas (vai para o rerank pairing), senão o
        # delta do filtro fica contaminado pelo efeito do rerank.
        revogadas_comparison = (
            revogadas_flags == {True, False}
            and len(rerank_flags) == 1
            and len(rerank_pools) <= 1
        )
        # Pareamento rerank: só roda quando há exatamente 2 configs
        # diferindo apenas em rerank. Com query_expansion ativo, são 4
        # configs e o rerank pairing é pulado em favor do QE pairing
        # (que considera as 4 combinações).
        if revogadas_comparison:
            from scripts.analyze_revogadas_pairing import (
                _config_by_filter,
                build_revogadas_pairing,
                render_revogadas_pairing_md,
            )

            revog_payload = json.loads(detail_path.read_text(encoding="utf-8"))
            revog_pairing = build_revogadas_pairing(
                _config_by_filter(revog_payload, exclude_revogadas=False),
                _config_by_filter(revog_payload, exclude_revogadas=True),
            )
            revog_json = output_dir / "revogadas_pairing.json"
            revog_json.write_text(
                json.dumps(revog_pairing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            revog_md = output_dir / "revogadas_pairing.md"
            revog_md.write_text(
                render_revogadas_pairing_md(revog_pairing), encoding="utf-8"
            )
            print(f"  Pareamento de revogadas salvo: {revog_json}")
            print(f"  Pareamento de revogadas legível: {revog_md}")
            print(
                f"    Filtro de revogadas: "
                f"{revog_pairing['decision_rule']['verdict']} "
                f"saved={revog_pairing['summary']['saved_count']} "
                f"broken={revog_pairing['summary']['broken_count']}"
            )
        elif pool_comparison:
            from scripts.analyze_rerank_pool_pairing import (
                _config_by_pool,
                build_pool_pairing,
                render_pool_pairing_md,
            )

            pool_payload = json.loads(detail_path.read_text(encoding="utf-8"))
            par1 = build_pool_pairing(
                _config_by_pool(pool_payload, rerank=True, pool=50),
                _config_by_pool(pool_payload, rerank=True, pool=100),
            )
            par2 = build_pool_pairing(
                _config_by_pool(pool_payload, rerank=False, pool=None),
                _config_by_pool(pool_payload, rerank=True, pool=100),
            )
            pool_pairing_json = output_dir / "rerank_pool_pairing.json"
            pool_pairing_json.write_text(
                json.dumps(
                    {"par1_pool_isolated": par1, "par2_vs_baseline": par2},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            pool_pairing_md = output_dir / "rerank_pool_pairing.md"
            pool_pairing_md.write_text(
                render_pool_pairing_md(par1, par2), encoding="utf-8"
            )
            print(f"  Pareamento de pool salvo: {pool_pairing_json}")
            print(f"  Pareamento de pool legível: {pool_pairing_md}")
            print(
                f"    Par 1 (pool50 vs pool100): "
                f"{par1['decision_rule']['verdict']} "
                f"saved={par1['summary']['saved_count']} "
                f"broken={par1['summary']['broken_count']}"
            )
        elif rerank_flags == {True, False} and qe_flags == {False}:
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

    # Manifesto do run (Marco A): registro auto-suficiente do que gerou estes
    # artefatos. Só no caminho de run fresco — `--from-cache` reaproveita um run
    # existente e não recalcula métricas/configs.
    if from_cache is None and aggregate is not None:
        artifact_paths = {
            "results_csv": "results.csv",
            "per_question": "per_question.json",
        }
        models = {
            "embedding_model": settings.EMBEDDING_MODEL,
            "rerank_model": settings.COHERE_RERANK_MODEL,
        }
        if args.mode == "rag":
            artifact_paths["failure_analysis_json"] = "failure_analysis.json"
            artifact_paths["failure_analysis_md"] = "failure_analysis.md"
            models["llm_model"] = settings.LLM_MODEL
            models["llm_judge_model"] = settings.LLM_JUDGE_MODEL
        manifest = build_run_manifest(
            mode=args.mode,
            run_id=run_id,
            aggregate=aggregate,
            top_k=args.top_k,
            ground_truth_version=gt_version,
            ground_truth_source=gt_source,
            num_questions=len(questions),
            num_skipped=len(result.skipped_questions),
            cache_stats=result.cache_stats,
            models=models,
            artifact_paths=artifact_paths,
        )
        manifest_path = write_run_manifest(output_dir, manifest)
        print(f"  Manifesto do run salvo: {manifest_path}")

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
