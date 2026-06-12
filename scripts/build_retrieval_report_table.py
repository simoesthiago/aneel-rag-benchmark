"""Gera a tabela comparativa limpa da matriz de retrieval (Marco B).

Lê o `results.csv` de um ou mais runs em `data/evaluation/runs/retrieval/` e
emite uma tabela curada (Markdown + CSV) em `data/evaluation/report/tables/`,
pronta para o relatório. Junta as metades sem rerank e com rerank quando ambos
os runs são passados, e registra proveniência (run_ids, versão do GT, commit)
no cabeçalho do Markdown.

Uso:

    python3 scripts/build_retrieval_report_table.py <run_dir> [<run_dir> ...]
    python3 scripts/build_retrieval_report_table.py \
        data/evaluation/runs/retrieval/20260612T225543Z-9f724e4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

# Colunas exibidas na tabela do relatório, em ordem de leitura.
DISPLAY_COLUMNS = [
    "model",
    "chunk_strategy",
    "metodo_extracao",
    "mode",
    "rerank",
    "recall_at_k",
    "doc_recall_at_k",
    "precision_at_k",
    "mrr_at_k",
    "ndcg_at_k",
    "latency_avg_ms",
]
ROUND_3 = ["recall_at_k", "doc_recall_at_k", "precision_at_k", "mrr_at_k", "ndcg_at_k"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "run_dirs",
        type=Path,
        nargs="+",
        help="Um ou mais diretórios de run de retrieval (com results.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/report/tables"),
        help="Diretório de saída (default: data/evaluation/report/tables).",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="retrieval_matrix",
        help="Nome-base dos arquivos de saída (default: retrieval_matrix).",
    )
    return parser.parse_args()


def _load_run(run_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Carrega results.csv + proveniência do manifest.json de um run."""
    df = pd.read_csv(run_dir / "results.csv")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    prov = {
        "run_id": manifest.get("run_id"),
        "gt_version": manifest.get("ground_truth", {}).get("version"),
        "git_commit": manifest.get("git_commit"),
        "top_k": manifest.get("top_k"),
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
        table["latency_avg_ms"] = table["latency_avg_ms"].round(1)
    # Melhor primeiro: recuperar o documento certo é o sinal principal; nDCG
    # desempata pela qualidade do ranking.
    table = table.sort_values(
        ["doc_recall_at_k", "ndcg_at_k"], ascending=False
    ).reset_index(drop=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"{args.name}.csv"
    md_path = args.output_dir / f"{args.name}.md"
    table.to_csv(csv_path, index=False)

    gt_versions = sorted({p["gt_version"] for p in provenance})
    lines = [
        "# Matriz de retrieval — comparativo (Marco B)",
        "",
        f"- Ground truth: {', '.join(v for v in gt_versions if v)}",
        f"- top_k: {provenance[0]['top_k']}",
        "- Filtros de higiene aplicados: `sem_revogadas + sem_versoes_antigas "
        "+ submodulo_exato`.",
        "- Ordenado por `doc_recall_at_k` (desc), desempate `ndcg_at_k`.",
        "- Proveniência (runs):",
    ]
    for prov in provenance:
        lines.append(
            f"  - `{prov['run_id']}` (commit `{prov['git_commit']}`)"
        )
    lines += ["", table.to_markdown(index=False), ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Tabela CSV salva: {csv_path}")
    print(f"Tabela Markdown salva: {md_path}")
    print(f"  {len(table)} configurações de {len(args.run_dirs)} run(s).")


if __name__ == "__main__":
    main()
