"""Opção A — Rerank na melhor config com candidates_k=100.

Hipótese: a Fase C (rerank com candidates_k=50, default) deixou gt-0030
fora do alcance (trecho em rank 82). Talvez outras perguntas do balde 3
estejam em rank 30-50 e tenham sido alcançadas, mas o ganho marginal
ficou diluído por casos não alcançáveis. Ampliando o pool para 100,
o reranker tem mais matéria-prima.

Compara 3 cenários na melhor config (large+fixed-size+markdown+flat):
1. Baseline (top-10 sem rerank)
2. Rerank com pool 50 (já testado na Fase C — re-roda para garantir
   consistência)
3. Rerank com pool 100 (NOVO)

Reaproveita o cache de embeddings entre as 3 execuções.

Saída: data/evaluation/results/diagnostic/rerank_pool_comparison.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/rerank_pool_comparison.md"
)


def avaliar(retriever: Retriever, questions: list) -> list[dict]:
    out = []
    for i, q in enumerate(questions, start=1):
        out.append(evaluate_question(retriever, q, top_k=TOP_K))
        if i % 10 == 0:
            print(f"  {i}/{len(questions)}", file=sys.stderr)
    return out


def agreg(rows: list[dict]) -> dict[str, float]:
    return {
        "passage_recall_at_k": sum(r["recall_at_k"] for r in rows) / len(rows),
        "doc_recall_at_k": sum(r["doc_recall_at_k"] for r in rows) / len(rows),
        "mrr_at_k": sum(r["mrr_at_k"] for r in rows) / len(rows),
        "ndcg_at_k": sum(r["ndcg_at_k"] for r in rows) / len(rows),
    }


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

    cache = QueryEmbeddingCache()
    common = dict(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        query_cache=cache,
    )

    print("Cenário 1: baseline (sem rerank) ...", file=sys.stderr)
    base = avaliar(Retriever(**common), questions)

    print("Cenário 2: rerank pool=50 (default) ...", file=sys.stderr)
    rerank50 = avaliar(
        Retriever(**common, reranker=CohereReranker()), questions
    )

    print("Cenário 3: rerank pool=100 (NOVO) ...", file=sys.stderr)
    rerank100 = avaliar(
        Retriever(
            **common,
            reranker=CohereReranker(),
            candidates_k=100,
        ),
        questions,
    )

    ag_base = agreg(base)
    ag_rr50 = agreg(rerank50)
    ag_rr100 = agreg(rerank100)

    # Análise por pergunta — quem virou acerto?
    def falhas(rows: list[dict]) -> set[str]:
        return {r["question_id"] for r in rows if r["recall_at_k"] == 0.0}

    f_base = falhas(base)
    f_rr50 = falhas(rerank50)
    f_rr100 = falhas(rerank100)

    def comparar(a: set, b: set) -> tuple[list, list]:
        salvos = sorted(a - b)
        quebrados = sorted(b - a)
        return salvos, quebrados

    salvos50, quebrados50 = comparar(f_base, f_rr50)
    salvos100, quebrados100 = comparar(f_base, f_rr100)
    salvos_a_mais_100, perdidos_a_mais_100 = comparar(f_rr50, f_rr100)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(
        "# Opção A — Rerank na melhor config: pool 50 vs pool 100\n"
    )
    lines.append(
        "Config: text-embedding-3-large + fixed-size + markdown + flat\n"
    )
    lines.append(f"Perguntas: {len(questions)}\n")

    lines.append("\n## Métricas agregadas\n")
    lines.append(
        "| métrica | base | +rerank (pool 50) | +rerank (pool 100) | "
        "Δ pool100 vs base |"
    )
    lines.append("|---|---:|---:|---:|---:|")
    for m in (
        "passage_recall_at_k",
        "doc_recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
    ):
        delta = ag_rr100[m] - ag_base[m]
        sinal = "+" if delta >= 0 else ""
        lines.append(
            f"| {m} | {ag_base[m]:.4f} | {ag_rr50[m]:.4f} "
            f"| {ag_rr100[m]:.4f} | {sinal}{delta:.4f} |"
        )

    lines.append("\n## Movimento de perguntas\n")
    lines.append(
        f"- **Pool 50 vs base**: salvos {salvos50 or 'nenhum'}; "
        f"quebrados {quebrados50 or 'nenhum'}"
    )
    lines.append(
        f"- **Pool 100 vs base**: salvos {salvos100 or 'nenhum'}; "
        f"quebrados {quebrados100 or 'nenhum'}"
    )
    lines.append(
        f"- **Pool 100 vs pool 50**: salvos a mais "
        f"{salvos_a_mais_100 or 'nenhum'}; perdidos a mais "
        f"{perdidos_a_mais_100 or 'nenhum'}"
    )

    lines.append("\n## Por balde (pool 100 vs base)\n")
    for nome, balde in (
        ("Balde 1 (doc não aparece)", FALHAS_BALDE_1),
        ("Balde 2 (doc aparece, trecho não)", FALHAS_BALDE_2),
        ("Balde 3 (trecho aparece, mas baixo)", FALHAS_BALDE_3),
    ):
        base_falham = sorted(balde & f_base)
        rr100_falham = sorted(balde & f_rr100)
        lines.append(
            f"- **{nome}**: base falha {base_falham}; "
            f"rerank pool 100 falha {rr100_falham}"
        )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Métricas agregadas ===")
    header = f"{'métrica':25s}  {'base':>8s}  {'rr p50':>8s}  {'rr p100':>8s}  {'Δp100':>8s}"
    print(header)
    for m in (
        "passage_recall_at_k",
        "doc_recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
    ):
        delta = ag_rr100[m] - ag_base[m]
        print(
            f"{m:25s}  {ag_base[m]:>8.4f}  {ag_rr50[m]:>8.4f}  "
            f"{ag_rr100[m]:>8.4f}  {delta:>+8.4f}"
        )
    print()
    print(f"Pool 100 salvou (vs base): {salvos100}")
    print(f"Pool 100 quebrou (vs base): {quebrados100}")
    print(f"Pool 100 salvou a MAIS (vs pool 50): {salvos_a_mais_100}")
    print(f"Pool 100 perdeu a MAIS (vs pool 50): {perdidos_a_mais_100}")
    print(f"\nCache: {cache.stats}")
    print(f"\nSaída salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
