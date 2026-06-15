"""Pareamento saved/broken do rerank nos finalistas RAG (Marco C).

Para cada estratégia de extração (markdown, texto), pareia `per_question` entre
a config sem rerank e com rerank (por `question_id`) e conta quantas perguntas
o rerank **salvou** (não-usável -> usável) vs **quebrou** (usável -> não-usável).
É a leitura honesta do efeito do rerank: nominal por pergunta, não só a média.

Lê o `per_question.json` de um run de finalistas e grava um resumo em
`data/evaluation/report/summaries/`.

Uso:

    python3 scripts/build_rag_finalists_pairing.py <run_dir_rag>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("run_dir", type=Path, help="Run RAG dos finalistas.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/report/summaries"),
    )
    parser.add_argument("--name", type=str, default="rag_finalists_rerank_pairing")
    return parser.parse_args()


def _usable_by_qid(config: dict) -> dict[str, bool]:
    return {
        q["question_id"]: bool(q.get("answer_usable"))
        for q in config["per_question"]
    }


def _pair_for_metodo(results: list[dict], metodo: str) -> dict | None:
    """Acha as configs (sem rerank, com rerank) de uma extração e pareia."""
    base = next(
        (c for c in results if c["metodo_extracao"] == metodo and not c["rerank"]),
        None,
    )
    rer = next(
        (c for c in results if c["metodo_extracao"] == metodo and c["rerank"]),
        None,
    )
    if base is None or rer is None:
        return None
    base_u = _usable_by_qid(base)
    rer_u = _usable_by_qid(rer)
    qids = sorted(set(base_u) & set(rer_u))
    saved, broken, stable_pass, stable_fail = [], [], [], []
    for qid in qids:
        b, r = base_u[qid], rer_u[qid]
        if not b and r:
            saved.append(qid)
        elif b and not r:
            broken.append(qid)
        elif b and r:
            stable_pass.append(qid)
        else:
            stable_fail.append(qid)
    return {
        "metodo": metodo,
        "base_usable": sum(base_u.values()),
        "rerank_usable": sum(rer_u.values()),
        "n": len(qids),
        "saved": saved,
        "broken": broken,
        "stable_pass": stable_pass,
        "stable_fail": stable_fail,
    }


def main() -> None:
    args = parse_args()
    payload = json.loads((args.run_dir / "per_question.json").read_text("utf-8"))
    results = payload["results"]
    manifest = json.loads((args.run_dir / "manifest.json").read_text("utf-8"))

    pairs = [
        p
        for metodo in ("markdown", "texto")
        if (p := _pair_for_metodo(results, metodo)) is not None
    ]

    lines = [
        "# Efeito do rerank nos finalistas RAG (saved/broken por pergunta)",
        "",
        f"- Run: `{manifest.get('run_id')}` (commit `{manifest.get('git_commit')}`)",
        f"- Ground truth: {manifest.get('ground_truth', {}).get('version')}",
        "- `saved` = não-usável sem rerank vira usável com rerank; "
        "`broken` = o contrário.",
        "",
        "| extração | usável s/ rerank | usável c/ rerank | salvas | quebradas | net |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for p in pairs:
        net = len(p["saved"]) - len(p["broken"])
        lines.append(
            f"| {p['metodo']} | {p['base_usable']}/{p['n']} | "
            f"{p['rerank_usable']}/{p['n']} | {len(p['saved'])} | "
            f"{len(p['broken'])} | {net:+d} |"
        )
    lines.append("")
    for p in pairs:
        lines += [
            f"## {p['metodo']}",
            "",
            f"- salvas pelo rerank: {', '.join(p['saved']) or '—'}",
            f"- quebradas pelo rerank: {', '.join(p['broken']) or '—'}",
            "",
        ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.output_dir / f"{args.name}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Resumo salvo: {md_path}")
    for p in pairs:
        net = len(p["saved"]) - len(p["broken"])
        print(
            f"  {p['metodo']}: saved={len(p['saved'])} broken={len(p['broken'])} "
            f"net={net:+d}"
        )


if __name__ == "__main__":
    main()
