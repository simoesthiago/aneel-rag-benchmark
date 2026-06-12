"""Fase F1.5 — diagnóstico retrieval-only da higiene de versão.

Este script não chama gerador nem juiz LLM. Ele mede apenas se a higiene de
versão + restrição de submódulo melhora o contexto recuperado nas 9 perguntas
do Grupo A. Útil quando a quota OpenAI bloqueia `answer_usable`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import (  # noqa: E402
    build_rag_baseline_configs,
    run_config,
    split_evaluation_questions,
)
from src.evaluation.ground_truth import load_ground_truth_jsonl  # noqa: E402

TOP_K = 10
CACHE_PATH = Path("data/evaluation/cache/query_embeddings.json")
GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")
OUT_PATH = Path("data/evaluation/results/rag-50/version_hygiene_retrieval.json")

GRUPO_A = {
    "gt-0002", "gt-0004", "gt-0017", "gt-0023", "gt-0024",
    "gt-0025", "gt-0026", "gt-0028", "gt-0029",
}


def _by_qid(result: dict) -> dict[str, dict]:
    return {q["question_id"]: q for q in result["per_question"]}


def main() -> None:
    questions = load_ground_truth_jsonl(GT_PATH)
    evaluation, _ = split_evaluation_questions(questions)
    grupo_a = [q for q in evaluation if q.get("question_id") in GRUPO_A]
    print(f"Perguntas Grupo A: {len(grupo_a)}")

    sem_higiene, com_higiene = build_rag_baseline_configs(
        version_hygiene_comparison=True
    )
    cache = QueryEmbeddingCache(persist_path=CACHE_PATH)

    print(f"  SEM higiene: {sem_higiene.label}")
    r_sem = run_config(sem_higiene, grupo_a, top_k=TOP_K, query_cache=cache)
    print(f"  COM higiene: {com_higiene.label}")
    r_com = run_config(com_higiene, grupo_a, top_k=TOP_K, query_cache=cache)
    cache.save()

    by_sem, by_com = _by_qid(r_sem), _by_qid(r_com)
    rows: list[dict] = []
    print("\n=== Retrieval Grupo A ===")
    for qid in sorted(GRUPO_A):
        s, c = by_sem[qid], by_com[qid]
        row = {
            "question_id": qid,
            "recall_sem": s["recall_at_k"],
            "recall_com": c["recall_at_k"],
            "doc_recall_sem": s["doc_recall_at_k"],
            "doc_recall_com": c["doc_recall_at_k"],
            "mrr_sem": s["mrr_at_k"],
            "mrr_com": c["mrr_at_k"],
            "ndcg_sem": s["ndcg_at_k"],
            "ndcg_com": c["ndcg_at_k"],
        }
        rows.append(row)
        print(
            f"  {qid}: recall {s['recall_at_k']:.2f}->{c['recall_at_k']:.2f}"
            f" | doc {s['doc_recall_at_k']:.2f}->{c['doc_recall_at_k']:.2f}"
            f" | mrr {s['mrr_at_k']:.2f}->{c['mrr_at_k']:.2f}"
            f" | ndcg {s['ndcg_at_k']:.2f}->{c['ndcg_at_k']:.2f}"
        )

    improved = [
        r["question_id"]
        for r in rows
        if (r["recall_com"], r["doc_recall_com"]) > (r["recall_sem"], r["doc_recall_sem"])
    ]
    regressed = [
        r["question_id"]
        for r in rows
        if (r["recall_com"], r["doc_recall_com"]) < (r["recall_sem"], r["doc_recall_sem"])
    ]
    print(f"\nMelhoradas: {improved}")
    print(f"Regredidas: {regressed}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "improved": improved,
                "regressed": regressed,
                "sem_summary": {
                    "recall_at_k": r_sem["recall_at_k"],
                    "doc_recall_at_k": r_sem["doc_recall_at_k"],
                    "mrr_at_k": r_sem["mrr_at_k"],
                    "ndcg_at_k": r_sem["ndcg_at_k"],
                },
                "com_summary": {
                    "recall_at_k": r_com["recall_at_k"],
                    "doc_recall_at_k": r_com["doc_recall_at_k"],
                    "mrr_at_k": r_com["mrr_at_k"],
                    "ndcg_at_k": r_com["ndcg_at_k"],
                },
                "per_question": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nDetalhe salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
