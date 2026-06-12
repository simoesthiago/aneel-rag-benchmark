"""Fase F1.5 — pareamento isolado da higiene de versão (rerank@100 + filtro de
revogadas, COM vs SEM higiene completa de versões PRORET).

Roda os 2 configs sobre TODAS as perguntas avaliáveis e pareia `answer_usable`
por pergunta, para detectar:
  - SALVAS (False->True): perguntas que a higiene corrige
  - QUEBRADAS (True->False): regressões (hard break candidato)

Critério pré-comprometido (ROADMAP F1.5, espelha a F1): promover a higiene SE
nenhuma pergunta hoje `usable` regredir por perda de `doc_recall` (hard break) —
um soft break (doc_recall intacto, ruído de citação) não bloqueia.

Carrega o GT local para refletir as edições da branch (gt-0002/gt-0004). Salva
o detalhe em data/evaluation/results/rag-50/version_hygiene_pairing.json.

Uso: .venv/bin/python scripts/diagnostics/diagnose_version_hygiene.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import (  # noqa: E402
    build_rag_baseline_configs,
    run_rag_config,
    split_evaluation_questions,
)
from src.evaluation.ground_truth import load_ground_truth_jsonl  # noqa: E402

TOP_K = 10
CACHE_PATH = Path("data/evaluation/cache/query_embeddings.json")
GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")
OUT_PATH = Path("data/evaluation/results/rag-50/version_hygiene_pairing.json")

# As 9 do Grupo A (residuais "sistema certo, bookkeeping de versão/citação").
GRUPO_A = {
    "gt-0002", "gt-0004", "gt-0017", "gt-0023", "gt-0024",
    "gt-0025", "gt-0026", "gt-0028", "gt-0029",
}


def _by_qid(result: dict) -> dict[str, dict]:
    return {q["question_id"]: q for q in result["per_question"]}


def _fmt_score(value) -> str:
    return "None" if value is None else f"{float(value):.2f}"


def main() -> None:
    questions = load_ground_truth_jsonl(GT_PATH)
    evaluation, _ = split_evaluation_questions(questions)
    print(f"GT local: {len(questions)} perguntas | avaliáveis: {len(evaluation)}")

    sem_higiene, com_higiene = build_rag_baseline_configs(
        version_hygiene_comparison=True
    )
    print(f"  SEM higiene: {sem_higiene.label}")
    print(f"  COM higiene: {com_higiene.label}")
    cache = QueryEmbeddingCache(persist_path=CACHE_PATH)

    print("\nRodando SEM higiene de versão ...")
    r_sem = run_rag_config(sem_higiene, evaluation, top_k=TOP_K, query_cache=cache)
    print("Rodando COM higiene de versão ...")
    r_com = run_rag_config(com_higiene, evaluation, top_k=TOP_K, query_cache=cache)
    cache.save()

    by_sem, by_com = _by_qid(r_sem), _by_qid(r_com)
    saved, broken, hard_broken, estaveis = [], [], [], []
    for qid in sorted(by_sem):
        a = bool(by_sem[qid]["answer_usable"])
        b = bool(by_com[qid]["answer_usable"])
        if not a and b:
            saved.append(qid)
        elif a and not b:
            broken.append(qid)
            # hard break = perdeu doc_recall (a higiene removeu doc necessário)
            if by_com[qid]["doc_recall_at_k"] < by_sem[qid]["doc_recall_at_k"]:
                hard_broken.append(qid)
        else:
            estaveis.append(qid)

    usable_sem = sum(bool(q["answer_usable"]) for q in by_sem.values())
    usable_com = sum(bool(q["answer_usable"]) for q in by_com.values())

    print("\n=== Pareamento (rerank@100+filtro: SEM vs COM higiene de versão) ===")
    print(f"  answer_usable: {usable_sem}/{len(by_sem)} -> {usable_com}/{len(by_com)}")
    print(f"  SALVAS (False->True): {saved}")
    print(f"  QUEBRADAS (True->False): {broken}")
    print(f"  HARD BREAKS (quebrou E perdeu doc_recall): {hard_broken}")
    print(f"  LLM status SEM: {r_sem.get('llm_status_counts')}")
    print(f"  LLM status COM: {r_com.get('llm_status_counts')}")
    print(f"  Gerador status SEM: {r_sem.get('generator_status_counts')}")
    print(f"  Gerador status COM: {r_com.get('generator_status_counts')}")
    verdict = "PROMOVER" if not hard_broken and saved else (
        "REVISAR" if hard_broken else "keep_baseline"
    )
    print(f"\n  veredito (sem hard break E salva>0): **{verdict}**")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "sem_config": r_sem.get("label"),
                "com_config": r_com.get("label"),
                "usable_sem": usable_sem,
                "usable_com": usable_com,
                "saved": saved,
                "broken": broken,
                "hard_broken": hard_broken,
                "llm_status_sem": r_sem.get("llm_status_counts"),
                "llm_status_com": r_com.get("llm_status_counts"),
                "generator_status_sem": r_sem.get("generator_status_counts"),
                "generator_status_com": r_com.get("generator_status_counts"),
                "per_question": {
                    qid: {
                        "sem": by_sem.get(qid),
                        "com": by_com.get(qid),
                    }
                    for qid in sorted(by_sem)
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== Detalhe das 9 do Grupo A ===")
    for qid in sorted(GRUPO_A):
        if qid not in by_sem:
            print(f"  {qid}: (não avaliável)")
            continue
        s, c = by_sem[qid], by_com[qid]
        print(
            f"  {qid}: usable {bool(s['answer_usable'])}->{bool(c['answer_usable'])}"
            f" | doc_recall {s['doc_recall_at_k']:.2f}->{c['doc_recall_at_k']:.2f}"
            f" | recall {s['recall_at_k']:.2f}->{c['recall_at_k']:.2f}"
            f" | cit {s['citation_accuracy']:.2f}->{c['citation_accuracy']:.2f}"
            f" | corr {_fmt_score(s.get('answer_correctness'))}->{_fmt_score(c.get('answer_correctness'))}"
        )
    print(f"\nDetalhe salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
