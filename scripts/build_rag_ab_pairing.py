"""Pareamento A/B (antes vs depois) da mesma config RAG (Marco D).

Compara dois runs RAG da MESMA config — tipicamente `antes` e `depois` de uma
mudança de gerador/prompt/citação — pareando `per_question` por `question_id` e
contando saved/broken. É a régua de promoção do Marco D: promover só se
`saved >= 2*broken` e sem queda de faithfulness.

Funciona tanto em runs reais quanto em replays (retrieval congelado), desde que
as duas pontas usem a mesma config.

Uso:

    python3 scripts/build_rag_ab_pairing.py <run_antes> <run_depois> \
        [--label <config_label>] [--name <saida>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROMOTE_RATIO = 2.0  # saved >= 2*broken (mesma régua das outras fases)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("before", type=Path, help="Run RAG antes (dir).")
    parser.add_argument("after", type=Path, help="Run RAG depois (dir).")
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Label da config a parear. Default: a 1ª config de cada run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/report/summaries"),
    )
    parser.add_argument("--name", type=str, default="rag_ab_pairing")
    return parser.parse_args()


def _pick_config(run_dir: Path, label: str | None) -> dict:
    payload = json.loads((run_dir / "per_question.json").read_text("utf-8"))
    results = payload["results"]
    if label is not None:
        match = next((c for c in results if c.get("label") == label), None)
        if match is None:
            # per_question.json não guarda `label`; cai para identificação por
            # campos da config quando o label não casa.
            match = next(
                (
                    c
                    for c in results
                    if _config_label(c) == label
                ),
                None,
            )
        if match is None:
            raise SystemExit(f"Config '{label}' não encontrada em {run_dir}.")
        return match
    if len(results) != 1:
        raise SystemExit(
            f"{run_dir} tem {len(results)} configs; passe --label para escolher."
        )
    return results[0]


def _config_label(config: dict) -> str:
    rerank = "+rerank" if config.get("rerank") else ""
    return (
        f"{config.get('model')}|{config.get('chunk_strategy')}|"
        f"{config.get('metodo_extracao')}|{config.get('mode')}{rerank}"
    )


def _by_qid(config: dict) -> dict[str, dict]:
    return {q["question_id"]: q for q in config["per_question"]}


def _faith_avg(config: dict) -> float:
    vals = [
        q["faithfulness"]
        for q in config["per_question"]
        if q.get("faithfulness") is not None
    ]
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> None:
    args = parse_args()
    before = _pick_config(args.before, args.label)
    after = _pick_config(args.after, args.label)
    b_by, a_by = _by_qid(before), _by_qid(after)
    qids = sorted(set(b_by) & set(a_by))

    saved, broken, stable_pass, stable_fail = [], [], [], []
    for qid in qids:
        b = bool(b_by[qid].get("answer_usable"))
        a = bool(a_by[qid].get("answer_usable"))
        if not b and a:
            saved.append(qid)
        elif b and not a:
            broken.append(qid)
        elif b and a:
            stable_pass.append(qid)
        else:
            stable_fail.append(qid)

    n_saved, n_broken = len(saved), len(broken)
    faith_before, faith_after = _faith_avg(before), _faith_avg(after)
    promote = n_saved >= PROMOTE_RATIO * n_broken and faith_after >= faith_before - 1e-9
    verdict = "promote" if promote else "keep"

    b_usable = sum(1 for q in before["per_question"] if q.get("answer_usable"))
    a_usable = sum(1 for q in after["per_question"] if q.get("answer_usable"))

    lines = [
        "# Pareamento A/B RAG (Marco D)",
        "",
        f"- antes:  `{args.before}` — usáveis {b_usable}/{len(b_by)}, "
        f"faithfulness {faith_before:.3f}",
        f"- depois: `{args.after}` — usáveis {a_usable}/{len(a_by)}, "
        f"faithfulness {faith_after:.3f}",
        f"- regra: promover se `saved >= {PROMOTE_RATIO:g}*broken` e "
        "faithfulness não cair.",
        "",
        f"**saved={n_saved} | broken={n_broken} | net={n_saved - n_broken:+d} "
        f"| veredito: {verdict.upper()}**",
        "",
        f"- salvas: {', '.join(saved) or '—'}",
        f"- quebradas: {', '.join(broken) or '—'}",
        f"- estáveis usáveis: {len(stable_pass)} | estáveis não-usáveis: "
        f"{len(stable_fail)}",
        "",
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.output_dir / f"{args.name}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Resumo salvo: {md_path}")
    print(
        f"  saved={n_saved} broken={n_broken} net={n_saved - n_broken:+d} "
        f"verdict={verdict} (faith {faith_before:.3f}->{faith_after:.3f})"
    )


if __name__ == "__main__":
    main()
