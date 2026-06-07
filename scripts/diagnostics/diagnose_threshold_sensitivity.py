"""A.6 - Sensibilidade ao SUPPORT_EXCERPT_TOKEN_THRESHOLD do matching.

Re-executa retrieval com top-k=100 na config #1 (a melhor: large + fixed-size
+ markdown + flat) e recalcula recall variando o threshold de cobertura de
tokens informativos do support_excerpt.

Hipótese H8: threshold = 0.6 está alto demais; matching falha por pouco em
casos onde o chunk semanticamente contém o trecho mas perde alguns tokens.

NÃO altera src/evaluation/benchmark.py nem o per_question.json existente.
NÃO persiste cache (memória apenas). NÃO inclui rerank.

Saída: data/evaluation/results/diagnostic/threshold_sensitivity.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

import src.evaluation.matching as matching  # noqa: E402
from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
from src.evaluation.matching import source_coverage  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

TOP_K_RETRIEVE = 100  # piscina grande para variar threshold a posteriori
TOP_K_EVAL = 10  # recall computado no top-10
THRESHOLDS = (0.30, 0.45, 0.60, 0.75, 0.90)
DEFAULT_THRESHOLD = 0.60  # valor atual em matching.py

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/threshold_sensitivity.md"
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

    print("Carregando melhor config (large+fixed-size+markdown+flat) ...",
          file=sys.stderr)
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
    )

    # Retrieve top-100 para cada pergunta — uma única passagem.
    print(
        f"Recuperando top-{TOP_K_RETRIEVE} para {len(questions)} perguntas...",
        file=sys.stderr,
    )
    cache_retrieved: list[tuple[str, list[dict], list[dict]]] = []
    for i, q in enumerate(questions, start=1):
        chunks = retriever.retrieve(q["question"], top_k=TOP_K_RETRIEVE)
        sources = list(q.get("relevant_sources") or [])
        cache_retrieved.append(
            (str(q.get("question_id") or ""), chunks, sources)
        )
        if i % 10 == 0:
            print(f"  {i}/{len(questions)}", file=sys.stderr)

    # Para cada threshold, monkeypatch e recompute.
    original_threshold = matching.SUPPORT_EXCERPT_TOKEN_THRESHOLD
    resultados: list[dict[str, object]] = []
    falhas_por_threshold: dict[float, list[str]] = {}
    try:
        for thr in THRESHOLDS:
            matching.SUPPORT_EXCERPT_TOKEN_THRESHOLD = thr
            recalls = []
            falhas = []
            for qid, chunks, sources in cache_retrieved:
                # recall@TOP_K_EVAL, equivalente ao source_coverage no top-10
                rec = source_coverage(chunks[:TOP_K_EVAL], sources)
                recalls.append(rec)
                if rec == 0.0:
                    falhas.append(qid)
            mean_recall = sum(recalls) / len(recalls) if recalls else 0.0
            resultados.append(
                {
                    "threshold": thr,
                    f"recall@{TOP_K_EVAL}": round(mean_recall, 4),
                    "n_failures": len(falhas),
                    "is_default": thr == DEFAULT_THRESHOLD,
                }
            )
            falhas_por_threshold[thr] = falhas
    finally:
        matching.SUPPORT_EXCERPT_TOKEN_THRESHOLD = original_threshold

    df = pd.DataFrame(resultados)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Sensibilidade ao SUPPORT_EXCERPT_TOKEN_THRESHOLD\n")
    lines.append(
        "Config: text-embedding-3-large + fixed-size + markdown + flat "
        f"(top-{TOP_K_EVAL}, sem rerank)\n"
    )
    lines.append("Valor atual em produção: **0.60**.\n")
    lines.append(df.to_markdown(index=False))
    lines.append("")

    # Diferenças entre thresholds: quem falha em 0.60 mas passa em 0.30?
    falhas_06 = set(falhas_por_threshold[DEFAULT_THRESHOLD])
    falhas_03 = set(falhas_por_threshold.get(0.30, []))
    salvos_baixando = falhas_06 - falhas_03
    surgindo_subindo = (
        set(falhas_por_threshold.get(0.90, [])) - falhas_06
    )

    lines.append("\n## Casos sensíveis ao threshold\n")
    lines.append(
        f"- Falham em 0.60 e passam em 0.30: "
        f"{sorted(salvos_baixando) if salvos_baixando else 'nenhum'}"
    )
    lines.append(
        f"- Passam em 0.60 e falham em 0.90: "
        f"{sorted(surgindo_subindo) if surgindo_subindo else 'nenhum'}"
    )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(df.to_string(index=False))
    print()
    print(f"Casos salvos baixando 0.60→0.30: {sorted(salvos_baixando)}")
    print(f"Casos perdidos subindo 0.60→0.90: {sorted(surgindo_subindo)}")
    print(f"\nTabela salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
