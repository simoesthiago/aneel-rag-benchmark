"""Pareamento entre dois `per_question.json` para comparar versões de prompt.

Diferente de `rerank_pairing`, que compara duas configs dentro do mesmo arquivo
(`rerank=False` vs `rerank=True`), este script compara o config baseline
(`rerank=False`) entre dois arquivos: um antes da mudança de prompt e outro
depois.

Buckets (mesma semântica do rerank pairing, trocando "rerank" por "prompt v2"):
  - saved_by_prompt_v2
  - broken_by_prompt_v2
  - stable_pass
  - stable_fail_same_type
  - stable_fail_changed_type

Uso:
    python scripts/analyze_prompt_pairing.py \\
        --v1 data/evaluation/results/rag-50/per_question_promptv1.json \\
        --v2 data/evaluation/results/rag-50/per_question.json \\
        --output-dir data/evaluation/results/rag-50/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PAIRING_BUCKETS = [
    "saved_by_prompt_v2",
    "broken_by_prompt_v2",
    "stable_pass",
    "stable_fail_same_type",
    "stable_fail_changed_type",
]


def _baseline_config(per_question_path: Path) -> dict[str, Any]:
    payload = json.loads(per_question_path.read_text(encoding="utf-8"))
    for cfg in payload.get("results") or []:
        if not bool(cfg.get("rerank")):
            return cfg
    raise ValueError(
        f"{per_question_path} não contém config baseline (rerank=False)."
    )


def _failure_type(question: dict[str, Any]) -> str:
    return str(question.get("failure_type") or "unknown_failure")


def _entry(qid: str, v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": qid,
        "v1_failure_type": _failure_type(v1),
        "v2_failure_type": _failure_type(v2),
        "v1_citation_accuracy": v1.get("citation_accuracy"),
        "v2_citation_accuracy": v2.get("citation_accuracy"),
        "v1_answer_correctness": v1.get("answer_correctness"),
        "v2_answer_correctness": v2.get("answer_correctness"),
        "v1_recall_at_k": v1.get("recall_at_k"),
        "v2_recall_at_k": v2.get("recall_at_k"),
    }


def build_prompt_pairing(v1_cfg: dict[str, Any], v2_cfg: dict[str, Any]) -> dict[str, Any]:
    v1_by_qid = {q["question_id"]: q for q in v1_cfg.get("per_question") or []}
    v2_by_qid = {q["question_id"]: q for q in v2_cfg.get("per_question") or []}

    only_v1 = sorted(set(v1_by_qid) - set(v2_by_qid))
    only_v2 = sorted(set(v2_by_qid) - set(v1_by_qid))
    if only_v1 or only_v2:
        raise ValueError(
            f"question_id assimétrico. Só em v1: {only_v1}; só em v2: {only_v2}"
        )

    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in PAIRING_BUCKETS}
    for qid in sorted(v1_by_qid):
        v1 = v1_by_qid[qid]
        v2 = v2_by_qid[qid]
        v1_ok = bool(v1.get("answer_usable"))
        v2_ok = bool(v2.get("answer_usable"))
        entry = _entry(qid, v1, v2)
        if v1_ok and v2_ok:
            buckets["stable_pass"].append(entry)
        elif not v1_ok and v2_ok:
            buckets["saved_by_prompt_v2"].append(entry)
        elif v1_ok and not v2_ok:
            buckets["broken_by_prompt_v2"].append(entry)
        else:
            if entry["v1_failure_type"] == entry["v2_failure_type"]:
                buckets["stable_fail_same_type"].append(entry)
            else:
                buckets["stable_fail_changed_type"].append(entry)

    def _counts_from_per_question(cfg: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        for q in cfg.get("per_question") or []:
            ft = str(q.get("failure_type") or "unknown_failure")
            out[ft] = out.get(ft, 0) + 1
        return out

    v1_counts = dict(v1_cfg.get("failure_type_counts") or {}) or _counts_from_per_question(v1_cfg)
    v2_counts = dict(v2_cfg.get("failure_type_counts") or {}) or _counts_from_per_question(v2_cfg)

    def _rate_from_per_question(cfg: dict[str, Any]) -> float | None:
        per_q = cfg.get("per_question") or []
        if not per_q:
            return None
        usable = sum(1 for q in per_q if bool(q.get("answer_usable")))
        return usable / len(per_q)

    saved = len(buckets["saved_by_prompt_v2"])
    broken = len(buckets["broken_by_prompt_v2"])

    # Regra de promoção (análoga ao rerank pairing): prompt v2 substitui v1
    # quando salva mais do que quebra (razão >= 2) e não piora `citation_failure`
    # nem `answer_quality_failure` agregadamente. Pré-comprometida antes de ver
    # os números desta rodada.
    promote_ratio = 2
    cit_v1 = v1_counts.get("citation_failure", 0) + v1_counts.get(
        "citation_and_answer_failure", 0
    )
    cit_v2 = v2_counts.get("citation_failure", 0) + v2_counts.get(
        "citation_and_answer_failure", 0
    )
    delta_citation = cit_v2 - cit_v1
    ans_v1 = v1_counts.get("answer_quality_failure", 0) + v1_counts.get(
        "citation_and_answer_failure", 0
    )
    ans_v2 = v2_counts.get("answer_quality_failure", 0) + v2_counts.get(
        "citation_and_answer_failure", 0
    )
    delta_answer = ans_v2 - ans_v1

    reasons: list[str] = []
    if saved < promote_ratio * broken:
        reasons.append(f"saved={saved} < {promote_ratio}*broken={promote_ratio*broken}")
    if delta_citation > 0:
        reasons.append(f"delta_citation_failures=+{delta_citation} (piorou)")
    if delta_answer > 0:
        reasons.append(f"delta_answer_failures=+{delta_answer} (piorou)")
    verdict = "promote" if not reasons else "keep_v1"

    return {
        "buckets": {n: {"count": len(items), "questions": items} for n, items in buckets.items()},
        "summary": {
            "saved_count": saved,
            "broken_count": broken,
            "net_delta": saved - broken,
            "v1_answer_usable_rate": v1_cfg.get("answer_usable_rate") or _rate_from_per_question(v1_cfg),
            "v2_answer_usable_rate": v2_cfg.get("answer_usable_rate") or _rate_from_per_question(v2_cfg),
            "v1_failure_type_counts": v1_counts,
            "v2_failure_type_counts": v2_counts,
            "delta_citation_failures": delta_citation,
            "delta_answer_failures": delta_answer,
        },
        "decision_rule": {
            "rule": (
                f"promover prompt v2 SE saved >= {promote_ratio}*broken E "
                "delta_citation_failures <= 0 E delta_answer_failures <= 0"
            ),
            "saved": saved,
            "broken": broken,
            "delta_citation_failures": delta_citation,
            "delta_answer_failures": delta_answer,
            "verdict": verdict,
            "reasons": reasons,
        },
    }


def render_prompt_pairing_md(pairing: dict[str, Any]) -> str:
    buckets = pairing.get("buckets") or {}
    summary = pairing.get("summary") or {}
    decision = pairing.get("decision_rule") or {}

    def _rate(key: str) -> str:
        value = summary.get(key)
        return "n/d" if value is None else f"{float(value):.3f}"

    lines = [
        "# Pareamento prompt v2 vs prompt v1 (config baseline, sem rerank)",
        "",
        "## Resumo",
        "",
        "| Bucket | Count |",
        "|---|---:|",
    ]
    for name in PAIRING_BUCKETS:
        lines.append(f"| `{name}` | {(buckets.get(name) or {}).get('count', 0)} |")
    lines.extend(
        [
            "",
            (
                f"`answer_usable_rate`: v1 {_rate('v1_answer_usable_rate')} -> "
                f"v2 {_rate('v2_answer_usable_rate')} "
                f"(net_delta={summary.get('net_delta', 0):+d})"
            ),
            (
                f"`citation_failures`: delta={summary.get('delta_citation_failures', 0):+d}"
            ),
            (
                f"`answer_failures`: delta={summary.get('delta_answer_failures', 0):+d}"
            ),
            "",
        ]
    )

    def _section(title: str, name: str) -> None:
        items = (buckets.get(name) or {}).get("questions") or []
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_Nenhuma pergunta neste bucket._")
            lines.append("")
            return
        for item in items:
            lines.append(
                f"- `{item['question_id']}`: {item['v1_failure_type']} -> {item['v2_failure_type']}"
            )
        lines.append("")

    _section("Salvas pelo prompt v2", "saved_by_prompt_v2")
    _section("Quebradas pelo prompt v2", "broken_by_prompt_v2")
    _section("Falhas estáveis com tipo diferente", "stable_fail_changed_type")

    lines.extend(
        [
            "## Veredito",
            "",
            f"Regra: {decision.get('rule')}",
            "",
            f"- saved: {decision.get('saved')}",
            f"- broken: {decision.get('broken')}",
            f"- delta_citation_failures: {decision.get('delta_citation_failures'):+d}",
            f"- delta_answer_failures: {decision.get('delta_answer_failures'):+d}",
            f"- veredito: **{decision.get('verdict')}**",
        ]
    )
    reasons = decision.get("reasons") or []
    if reasons:
        lines.append("- razões:")
        for reason in reasons:
            lines.append(f"  - {reason}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", type=Path, required=True, help="per_question.json antes")
    parser.add_argument("--v2", type=Path, required=True, help="per_question.json depois")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results/rag-50"),
        help="diretório onde gravar prompt_pairing.{json,md}",
    )
    args = parser.parse_args()

    v1_cfg = _baseline_config(args.v1)
    v2_cfg = _baseline_config(args.v2)
    pairing = build_prompt_pairing(v1_cfg, v2_cfg)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "prompt_pairing.json").write_text(
        json.dumps(pairing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "prompt_pairing.md").write_text(
        render_prompt_pairing_md(pairing), encoding="utf-8"
    )
    print(f"Pareamento salvo em {args.output_dir / 'prompt_pairing.md'}")
    print(f"  saved={pairing['summary']['saved_count']} | broken={pairing['summary']['broken_count']}")
    print(f"  veredito={pairing['decision_rule']['verdict']}")


if __name__ == "__main__":
    main()
