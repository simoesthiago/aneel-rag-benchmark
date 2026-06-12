"""Fase F1.5 — confirmação final: pipeline promovido (rerank@100 + filtro de
revogadas + higiene de versão) contra o GT LOCAL já editado (gt-0004 any_of REN
1059, gt-0002 6.8 v1.10c).

Carrega o JSONL local (não o Hub) para refletir as edições do Gate 2. Roda 1
config sobre todas as perguntas avaliáveis e reporta:
  - answer_usable total (vs baseline canônico 33/48)
  - detalhe das 9 do Grupo A: quais viraram usable

Uso: .venv/bin/python scripts/diagnostics/diagnose_version_hygiene_final.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import (  # noqa: E402
    StoreConfig,
    run_rag_config,
    split_evaluation_questions,
)
from src.evaluation.ground_truth import load_ground_truth_jsonl  # noqa: E402

TOP_K = 10
CACHE_PATH = Path("data/evaluation/cache/query_embeddings.json")
GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")
OUT_PATH = Path("data/evaluation/results/rag-50/version_hygiene_final.json")

GRUPO_A = {
    "gt-0002", "gt-0004", "gt-0017", "gt-0023", "gt-0024",
    "gt-0025", "gt-0026", "gt-0028", "gt-0029",
}


def _fmt_score(value) -> str:
    return "None" if value is None else f"{float(value):.2f}"


def main() -> None:
    questions = load_ground_truth_jsonl(GT_PATH)
    evaluation, _ = split_evaluation_questions(questions)
    print(f"GT local: {len(questions)} perguntas | avaliáveis: {len(evaluation)}")

    config = StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        rerank=True,
        candidates_k_override=100,
        exclude_revogadas=True,
        exclude_superseded_versions=True,
        restrict_to_query_submodulo=True,
    )
    print(f"Config: {config.label}")
    cache = QueryEmbeddingCache(persist_path=CACHE_PATH)

    print("\nRodando pipeline promovido (higiene + GT editado) ...")
    result = run_rag_config(config, evaluation, top_k=TOP_K, query_cache=cache)
    cache.save()

    by = {q["question_id"]: q for q in result["per_question"]}
    usable = sorted(q for q, v in by.items() if bool(v["answer_usable"]))
    print(f"\n=== answer_usable: {len(usable)}/{len(by)} ===")
    print(f"LLM status: {result.get('llm_status_counts')}")
    print(f"Gerador status: {result.get('generator_status_counts')}")

    print("\n=== Detalhe das 9 do Grupo A ===")
    flipped = []
    for qid in sorted(GRUPO_A):
        v = by.get(qid)
        if v is None:
            print(f"  {qid}: (não avaliável)")
            continue
        u = bool(v["answer_usable"])
        if u:
            flipped.append(qid)
        print(
            f"  {qid}: usable={u}"
            f" | doc_recall {v['doc_recall_at_k']:.2f}"
            f" | recall {v['recall_at_k']:.2f}"
            f" | cit {v['citation_accuracy']:.2f}"
            f" | corr {_fmt_score(v.get('answer_correctness'))}"
        )
    print(f"\nGrupo A agora usable ({len(flipped)}/9): {flipped}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "usable_total": len(usable),
                "n": len(by),
                "llm_status": result.get("llm_status_counts"),
                "generator_status": result.get("generator_status_counts"),
                "usable_qids": usable,
                "grupo_a_usable": flipped,
                "per_question": by,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nDetalhe salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
