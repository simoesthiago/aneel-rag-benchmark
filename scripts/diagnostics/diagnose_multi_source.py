"""A.4 - Contagem de fontes múltiplas no ground truth.

Conta `len(relevant_sources)` por pergunta e cruza com as 11 falhas residuais
da melhor config. Hipótese: falhas concentradas em perguntas multi-fonte
indicam que o sistema é forte mas a métrica `source_coverage` (que exige
cobertura de todas as fontes) é binária demais.

Hipótese coberta: H9.
Saída: data/evaluation/results/diagnostic/multi_source_distribution.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402

FALHAS_BEST_CONFIG = {
    "gt-0002",
    "gt-0005",
    "gt-0007",
    "gt-0012",
    "gt-0017",
    "gt-0025",
    "gt-0026",
    "gt-0027",
    "gt-0029",
    "gt-0030",
    "gt-0034",
}

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/multi_source_distribution.md"
)


def main() -> None:
    questions = load_ground_truth_hub()

    distrib_total: Counter[int] = Counter()
    distrib_falhas: Counter[int] = Counter()
    detalhes: list[dict[str, object]] = []
    for q in questions:
        n_sources = len(q.get("relevant_sources") or [])
        qid = q.get("question_id") or ""
        distrib_total[n_sources] += 1
        if qid in FALHAS_BEST_CONFIG:
            distrib_falhas[n_sources] += 1
        detalhes.append(
            {
                "question_id": qid,
                "answerability": q.get("answerability"),
                "n_sources": n_sources,
                "is_failure": qid in FALHAS_BEST_CONFIG,
            }
        )

    df = pd.DataFrame(detalhes)
    df_falhas = df[df["is_failure"]].sort_values(
        ["n_sources", "question_id"]
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Distribuição de fontes por pergunta no ground truth\n")
    lines.append("## Distribuição global\n")
    lines.append("| n_sources | total | falhas (11) |")
    lines.append("|---:|---:|---:|")
    for n in sorted(set(distrib_total) | set(distrib_falhas)):
        lines.append(
            f"| {n} | {distrib_total.get(n, 0)} "
            f"| {distrib_falhas.get(n, 0)} |"
        )
    lines.append("")
    lines.append("## Detalhe das 11 falhas\n")
    lines.append("| question_id | answerability | n_sources |")
    lines.append("|---|---|---:|")
    for _, row in df_falhas.iterrows():
        lines.append(
            f"| {row['question_id']} | {row['answerability']} "
            f"| {row['n_sources']} |"
        )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== Distribuição global de n_sources ===")
    print(f"{'n':>3s}  {'total':>6s}  {'falhas/11':>10s}")
    for n in sorted(set(distrib_total) | set(distrib_falhas)):
        print(
            f"{n:>3d}  {distrib_total.get(n, 0):>6d}  "
            f"{distrib_falhas.get(n, 0):>10d}"
        )

    print()
    multi_source_falhas = sum(
        v for n, v in distrib_falhas.items() if n > 1
    )
    multi_source_total = sum(v for n, v in distrib_total.items() if n > 1)
    if multi_source_total:
        pct_falhas_que_multi = multi_source_falhas / 11 * 100
        pct_multi_falham = (
            multi_source_falhas / multi_source_total * 100
        )
        print(
            f"  {multi_source_falhas}/11 ({pct_falhas_que_multi:.0f}%) "
            "das falhas são perguntas multi-fonte."
        )
        print(
            f"  {multi_source_falhas}/{multi_source_total} "
            f"({pct_multi_falham:.0f}%) das perguntas multi-fonte falharam."
        )
    print()
    print(f"Tabela salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
