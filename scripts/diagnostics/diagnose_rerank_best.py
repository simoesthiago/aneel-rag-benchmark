"""Fase C — Teste de rerank apenas na melhor config (H1).

Roda a melhor config (text-embedding-3-large + fixed-size + markdown + flat)
com e sem Cohere Rerank 3, sobre as 48 perguntas avaliáveis. Compara
passage_recall@10 e doc_recall@10 para validar H1: rerank promove o trecho
correto dos casos do balde 3 (trecho rank 15-82) para o top-10.

Reaproveita o cache de embeddings entre as duas chamadas (queries iguais).
Usa --rate-limit-friendly: o CohereReranker tem retry+backoff agora; mesmo
em trial (10 req/min), 48 calls ≈ 5 min se nada falhar.

Saída: data/evaluation/results/diagnostic/rerank_best_comparison.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.benchmark import evaluate_question  # noqa: E402
from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
from src.rag.reranker import CohereReranker  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

TOP_K = 10
FALHAS_BALDE_3 = {
    "gt-0007",
    "gt-0012",
    "gt-0026",
    "gt-0029",
    "gt-0030",
}
FALHAS_BALDE_1 = {"gt-0002", "gt-0027"}
FALHAS_BALDE_2 = {"gt-0005", "gt-0017", "gt-0025", "gt-0034"}
FALHAS_TODAS = FALHAS_BALDE_1 | FALHAS_BALDE_2 | FALHAS_BALDE_3

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/rerank_best_comparison.md"
)


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    questions = load_ground_truth_hub()
    questions = [
        q
        for q in questions
        if str(q.get("answerability") or "corpus_supported")
        == "corpus_supported"
    ]
    print(f"  {len(questions)} perguntas avaliáveis.", file=sys.stderr)

    # Cache compartilhado entre as duas execuções (queries iguais → cache hit
    # 100% na segunda)
    cache = QueryEmbeddingCache()

    print("Rodando melhor config SEM rerank ...", file=sys.stderr)
    retriever_base = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        query_cache=cache,
    )
    metricas_base = [
        evaluate_question(retriever_base, q, top_k=TOP_K)
        for q in questions
    ]

    print("Rodando melhor config COM rerank Cohere ...", file=sys.stderr)
    retriever_rerank = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        query_cache=cache,
        reranker=CohereReranker(),
    )
    metricas_rerank = []
    for i, q in enumerate(questions, start=1):
        metricas_rerank.append(
            evaluate_question(retriever_rerank, q, top_k=TOP_K)
        )
        if i % 10 == 0:
            print(f"  rerank {i}/{len(questions)}", file=sys.stderr)

    # Agregação
    def agreg(rows: list[dict]) -> dict[str, float]:
        return {
            "passage_recall_at_k": sum(
                r["recall_at_k"] for r in rows
            )
            / len(rows),
            "doc_recall_at_k": sum(
                r["doc_recall_at_k"] for r in rows
            )
            / len(rows),
            "mrr_at_k": sum(r["mrr_at_k"] for r in rows) / len(rows),
            "ndcg_at_k": sum(r["ndcg_at_k"] for r in rows) / len(rows),
        }

    ag_base = agreg(metricas_base)
    ag_rerank = agreg(metricas_rerank)

    # Análise por pergunta — quem virou acerto?
    by_qid_base = {r["question_id"]: r for r in metricas_base}
    by_qid_rerank = {r["question_id"]: r for r in metricas_rerank}
    falhas_base = {
        qid for qid, r in by_qid_base.items() if r["recall_at_k"] == 0.0
    }
    falhas_rerank = {
        qid for qid, r in by_qid_rerank.items() if r["recall_at_k"] == 0.0
    }
    salvos_pelo_rerank = falhas_base - falhas_rerank
    quebrados_pelo_rerank = falhas_rerank - falhas_base

    # Por balde
    def status_balde(balde: set[str]) -> str:
        base_falham = balde & falhas_base
        rerank_falham = balde & falhas_rerank
        return (
            f"falhas base: {len(base_falham)}/{len(balde)} "
            f"({sorted(base_falham)}); "
            f"falhas rerank: {len(rerank_falham)}/{len(balde)} "
            f"({sorted(rerank_falham)})"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Fase C — Rerank Cohere na melhor config\n")
    lines.append(
        "Config: text-embedding-3-large + fixed-size + markdown + flat\n"
    )
    lines.append(f"Perguntas avaliáveis: {len(questions)}\n")

    lines.append("\n## Métricas agregadas\n")
    lines.append("| métrica | base | +rerank | delta |")
    lines.append("|---|---:|---:|---:|")
    for m in (
        "passage_recall_at_k",
        "doc_recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
    ):
        delta = ag_rerank[m] - ag_base[m]
        sinal = "+" if delta >= 0 else ""
        lines.append(
            f"| {m} | {ag_base[m]:.4f} | {ag_rerank[m]:.4f} "
            f"| {sinal}{delta:.4f} |"
        )

    lines.append("\n## Por balde de falha\n")
    lines.append(f"- **Balde 1 (doc não aparece):** {status_balde(FALHAS_BALDE_1)}")
    lines.append(f"- **Balde 2 (doc aparece, trecho não):** {status_balde(FALHAS_BALDE_2)}")
    lines.append(f"- **Balde 3 (trecho aparece, mas baixo):** {status_balde(FALHAS_BALDE_3)}")

    lines.append("\n## Movimento de perguntas\n")
    lines.append(f"- Salvos pelo rerank: {sorted(salvos_pelo_rerank) or 'nenhum'}")
    lines.append(f"- Quebrados pelo rerank: {sorted(quebrados_pelo_rerank) or 'nenhum'}")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Métricas agregadas ===")
    print(
        f"{'métrica':25s}  {'base':>8s}  {'+rerank':>8s}  {'delta':>8s}"
    )
    for m in (
        "passage_recall_at_k",
        "doc_recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
    ):
        delta = ag_rerank[m] - ag_base[m]
        print(
            f"{m:25s}  {ag_base[m]:>8.4f}  {ag_rerank[m]:>8.4f}  "
            f"{delta:>+8.4f}"
        )
    print()
    print(f"Balde 1: {status_balde(FALHAS_BALDE_1)}")
    print(f"Balde 2: {status_balde(FALHAS_BALDE_2)}")
    print(f"Balde 3: {status_balde(FALHAS_BALDE_3)}")
    print(f"\nSalvos pelo rerank: {sorted(salvos_pelo_rerank)}")
    print(f"Quebrados pelo rerank: {sorted(quebrados_pelo_rerank)}")
    print(f"\nCache: {cache.stats}")
    print(f"\nSaída salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
