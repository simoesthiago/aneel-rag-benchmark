"""Fase 5 — validação isolada do boost de identificador (econômica).

O boost é no-op comprovado para perguntas que NÃO citam submódulo (o retriever
devolve os candidatos inalterados), então só essas podem mudar. Rodamos os 2
configs (pipeline ± boost) **apenas nas perguntas que citam submódulo** e
pareamos `answer_usable` — minimizando o gasto de quota Cohere/OpenAI.

Critério pré-comprometido (ROADMAP F5): promover o boost SE `saved >= 2*broken`.

Uso: .venv/bin/python scripts/diagnostics/diagnose_f5_boost.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import (  # noqa: E402
    build_rag_baseline_configs,
    run_rag_config,
    split_evaluation_questions,
)
from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
from src.rag.identifier_match import query_submodulo_id  # noqa: E402

TOP_K = 10
CACHE_PATH = Path("data/evaluation/cache/query_embeddings.json")


def _usable_by_qid(result: dict) -> dict[str, bool]:
    return {
        q["question_id"]: bool(q["answer_usable"]) for q in result["per_question"]
    }


def main() -> None:
    questions = load_ground_truth_hub()
    evaluation, _ = split_evaluation_questions(questions)
    # só perguntas que citam submódulo (as demais são no-op do boost)
    alvo = [q for q in evaluation if query_submodulo_id(q["question"])]
    print(f"Perguntas com submódulo (avaliáveis): {len(alvo)} -> "
          f"{[q['question_id'] for q in alvo]}")

    sem_boost, com_boost = build_rag_baseline_configs(
        boost_identificador_comparison=True
    )
    cache = QueryEmbeddingCache(persist_path=CACHE_PATH)

    print("\nRodando SEM boost ...")
    r_sem = run_rag_config(sem_boost, alvo, top_k=TOP_K, query_cache=cache)
    print("Rodando COM boost ...")
    r_com = run_rag_config(com_boost, alvo, top_k=TOP_K, query_cache=cache)
    cache.save()

    u_sem, u_com = _usable_by_qid(r_sem), _usable_by_qid(r_com)
    saved, broken, estaveis = [], [], []
    for qid in sorted(u_sem):
        a, b = u_sem[qid], u_com[qid]
        if not a and b:
            saved.append(qid)
        elif a and not b:
            broken.append(qid)
        else:
            estaveis.append((qid, a))

    print("\n=== Pareamento (pipeline sem boost vs com boost) ===")
    print(f"  SALVAS (False->True): {saved}")
    print(f"  QUEBRADAS (True->False): {broken}")
    print(f"  estáveis: {[q for q, _ in estaveis]}")
    verdict = "PROMOVER" if len(saved) >= 2 * len(broken) and saved else (
        "keep_baseline"
    )
    print(f"\n  saved={len(saved)} broken={len(broken)} "
          f"-> critério saved>=2*broken: **{verdict}**")

    # detalhe por pergunta-alvo
    by_sem = {q["question_id"]: q for q in r_sem["per_question"]}
    by_com = {q["question_id"]: q for q in r_com["per_question"]}
    print("\n=== Detalhe ===")
    for qid in sorted(u_sem):
        s, c = by_sem[qid], by_com[qid]
        print(f"  {qid}: usable {u_sem[qid]}->{u_com[qid]} | "
              f"doc_recall {s['doc_recall_at_k']:.2f}->{c['doc_recall_at_k']:.2f} | "
              f"recall {s['recall_at_k']:.2f}->{c['recall_at_k']:.2f} | "
              f"cit {s['citation_accuracy']:.2f}->{c['citation_accuracy']:.2f}")


if __name__ == "__main__":
    main()
