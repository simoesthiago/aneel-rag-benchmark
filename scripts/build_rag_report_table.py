"""Gera a tabela comparativa dos finalistas RAG (Marco C).

Lê o `results.csv` de um run RAG em `data/evaluation/runs/rag/` e emite uma
tabela curada (Markdown + CSV) em `data/evaluation/report/tables/`, focada nas
métricas de resposta final (answer_usable, citação, correção, fidelidade) além
de recall/nDCG e latência. Proveniência (run_id, GT, commit) no cabeçalho.

Uso:

    python3 scripts/build_rag_report_table.py <run_dir> [<run_dir> ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

# Métricas de resposta final primeiro (o que o Marco C compara), depois
# retrieval e custo.
DISPLAY_COLUMNS = [
    "model",
    "metodo_extracao",
    "rerank",
    "answer_usable_rate",
    "citation_accuracy_avg",
    "answer_correctness_avg",
    "faithfulness_avg",
    "recall_at_k",
    "doc_recall_at_k",
    "ndcg_at_k",
    "latency_avg_ms",
]
ROUND_3 = [
    "answer_usable_rate",
    "citation_accuracy_avg",
    "answer_correctness_avg",
    "faithfulness_avg",
    "recall_at_k",
    "doc_recall_at_k",
    "ndcg_at_k",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("run_dirs", type=Path, nargs="+", help="Run(s) RAG.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/report/tables"),
    )
    parser.add_argument("--name", type=str, default="rag_finalists")
    return parser.parse_args()


def _load_run(run_dir: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(run_dir / "results.csv")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    prov = {
        "run_id": manifest.get("run_id"),
        "gt_version": manifest.get("ground_truth", {}).get("version"),
        "git_commit": manifest.get("git_commit"),
        "top_k": manifest.get("top_k"),
        "llm_model": manifest.get("models", {}).get("llm_model"),
        "llm_judge_model": manifest.get("models", {}).get("llm_judge_model"),
    }
    return df, prov


def main() -> None:
    args = parse_args()
    frames: list[pd.DataFrame] = []
    provenance: list[dict] = []
    for run_dir in args.run_dirs:
        df, prov = _load_run(run_dir)
        frames.append(df)
        provenance.append(prov)

    combined = pd.concat(frames, ignore_index=True)
    table = combined[[c for c in DISPLAY_COLUMNS if c in combined.columns]].copy()
    for col in ROUND_3:
        if col in table.columns:
            table[col] = table[col].round(3)
    if "latency_avg_ms" in table.columns:
        table["latency_avg_ms"] = table["latency_avg_ms"].round(0)
    # Melhor primeiro: usabilidade final é o gate do projeto.
    table = table.sort_values(
        ["answer_usable_rate", "ndcg_at_k"], ascending=False
    ).reset_index(drop=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"{args.name}.csv"
    md_path = args.output_dir / f"{args.name}.md"
    table.to_csv(csv_path, index=False)

    gt_versions = sorted({p["gt_version"] for p in provenance})
    lines = [
        "# Finalistas RAG — comparativo (Marco C)",
        "",
        f"- Ground truth: {', '.join(v for v in gt_versions if v)}",
        f"- top_k: {provenance[0]['top_k']}",
        f"- Gerador: {provenance[0]['llm_model']} | Juiz: "
        f"{provenance[0]['llm_judge_model']}",
        "- `answer_usable = recall>0 AND citation>=0.5 AND correctness>=0.8`.",
        "- Configs com rerank usam `rerank@100` + higiene "
        "(`sem_revogadas + sem_versoes_antigas + submodulo_exato`).",
        "- Ordenado por `answer_usable_rate` (desc), desempate `ndcg_at_k`.",
        "- Proveniência (runs):",
    ]
    for prov in provenance:
        lines.append(f"  - `{prov['run_id']}` (commit `{prov['git_commit']}`)")
    lines += ["", table.to_markdown(index=False), ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Tabela CSV salva: {csv_path}")
    print(f"Tabela Markdown salva: {md_path}")
    print(f"  {len(table)} configurações de {len(args.run_dirs)} run(s).")


if __name__ == "__main__":
    main()
