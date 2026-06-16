"""Monta a matriz de retrieval final (v2) curada para o relatório.

Combina, com proveniência explícita:
  - linhas `fixed-size` do run oficial do Marco B (v1) — intocadas;
  - linhas estruturais (`article-aware`, `hierarchical-child`) do run v2, gerado
    com o parser/splitter corrigidos (H12) e stores do repo
    `simoesthiago/aneel-vectorstores-h12`.

`fixed-size` não usa o splitter, então segue do v1. As estruturais aparecem no
seu melhor caso honesto (v2). Uma coluna `fonte` rotula a origem de cada linha.

Uso:
    python scripts/build_retrieval_matrix_v2.py <run_v1> <run_v2>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

RUN_V1 = "data/evaluation/runs/retrieval/20260614T161535Z-18d8e21"
RUN_V2 = "data/evaluation/runs/retrieval/20260616T033915Z-5e61c8f-dirty"
OUT_DIR = Path("data/evaluation/report/tables")
NAME = "retrieval_matrix_v2"

DISPLAY = [
    "fonte", "model", "chunk_strategy", "metodo_extracao", "mode", "rerank",
    "recall_at_k", "doc_recall_at_k", "precision_at_k", "mrr_at_k",
    "ndcg_at_k", "latency_avg_ms",
]
ROUND_3 = ["recall_at_k", "doc_recall_at_k", "precision_at_k", "mrr_at_k", "ndcg_at_k"]
STRUCTURAL = {"article-aware", "hierarchical-child"}


def _load(run_dir: str) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(Path(run_dir) / "results.csv")
    m = json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))
    prov = {
        "run_id": m.get("run_id"),
        "gt": m.get("ground_truth", {}).get("version"),
        "commit": m.get("git_commit"),
        "top_k": m.get("top_k"),
    }
    return df, prov


def main() -> None:
    run_v1 = sys.argv[1] if len(sys.argv) > 1 else RUN_V1
    run_v2 = sys.argv[2] if len(sys.argv) > 2 else RUN_V2

    df1, p1 = _load(run_v1)
    df2, p2 = _load(run_v2)

    fixed = df1[df1["chunk_strategy"] == "fixed-size"].copy()
    fixed["fonte"] = "v1 (Marco B)"
    estrut = df2[df2["chunk_strategy"].isin(STRUCTURAL)].copy()
    estrut["fonte"] = "v2 (parser+splitter H12)"

    table = pd.concat([fixed, estrut], ignore_index=True)
    table = table[[c for c in DISPLAY if c in table.columns]]
    for col in ROUND_3:
        table[col] = table[col].round(3)
    table["latency_avg_ms"] = table["latency_avg_ms"].round(1)
    table = table.sort_values(
        ["doc_recall_at_k", "ndcg_at_k"], ascending=False
    ).reset_index(drop=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / f"{NAME}.csv", index=False)

    lines = [
        "# Matriz de retrieval — final v2 (pós-correção de chunking H12)",
        "",
        f"- Ground truth: {p2['gt']} | top_k: {p2['top_k']} | 48 perguntas "
        "avaliáveis (2 source_only fora do agregado).",
        "- Filtros de higiene: `sem_revogadas + sem_versoes_antigas + submodulo_exato`.",
        "- `fixed-size` vem do run v1 (não usa o splitter corrigido); estratégias "
        "estruturais vêm do run v2 (parser + splitter markdown-aware + merge).",
        "- Ordenado por `doc_recall_at_k` (desc), desempate `ndcg_at_k`.",
        "- Proveniência:",
        f"  - v1 `{p1['run_id']}` (commit `{p1['commit']}`) — fixed-size.",
        f"  - v2 `{p2['run_id']}` (commit `{p2['commit']}`) — estruturais; "
        "stores em `simoesthiago/aneel-vectorstores-h12`.",
        "",
        table.to_markdown(index=False),
        "",
    ]
    (OUT_DIR / f"{NAME}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Tabela salva: {OUT_DIR / f'{NAME}.md'} ({len(table)} configs)")


if __name__ == "__main__":
    main()
