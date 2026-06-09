"""Pareamento de query expansion (QE) dentro de um único `per_question.json`.

Diferente de `analyze_prompt_pairing.py` (que compara dois arquivos), este
script lê 1 arquivo contendo 4 configs e produz DOIS pareamentos
independentes:

  Par 1 — efeito de QE sobre o baseline puro:
    config (rerank=False, qe=False) vs config (rerank=False, qe=True)

  Par 2 — efeito de QE sobre o baseline+rerank:
    config (rerank=True, qe=False) vs config (rerank=True, qe=True)

Cada par aplica o critério pré-comprometido independentemente. Os 5 buckets
são iguais ao prompt_pairing (saved/broken/stable_pass/stable_fail_{same,
changed}_type).

Uso:
    python scripts/analyze_query_expansion_pairing.py \\
        --per-question data/evaluation/results/rag-50/per_question.json \\
        --output-dir data/evaluation/results/rag-50/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PAIRING_BUCKETS = [
    "saved_by_qe",
    "broken_by_qe",
    "stable_pass",
    "stable_fail_same_type",
    "stable_fail_changed_type",
]


def _config_by_flags(payload: dict[str, Any], *, rerank: bool, qe: bool) -> dict[str, Any]:
    for cfg in payload.get("results") or []:
        if bool(cfg.get("rerank")) == rerank and bool(cfg.get("query_expansion")) == qe:
            return cfg
    raise ValueError(
        f"Config não encontrada: rerank={rerank}, query_expansion={qe}. "
        "Rode `--mode rag --query-expansion` para gerar as 4 configs."
    )


def _failure_type(question: dict[str, Any]) -> str:
    return str(question.get("failure_type") or "unknown_failure")


def _entry(qid: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": qid,
        "before_failure_type": _failure_type(before),
        "after_failure_type": _failure_type(after),
        "before_recall_at_k": before.get("recall_at_k"),
        "after_recall_at_k": after.get("recall_at_k"),
        "before_doc_recall_at_k": before.get("doc_recall_at_k"),
        "after_doc_recall_at_k": after.get("doc_recall_at_k"),
        "expanded_query": after.get("expanded_query"),
        "query_expansion_status": after.get("query_expansion_status"),
    }


def _counts(cfg: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in cfg.get("per_question") or []:
        ft = str(q.get("failure_type") or "unknown_failure")
        out[ft] = out.get(ft, 0) + 1
    return out


def _rate(cfg: dict[str, Any]) -> float | None:
    per_q = cfg.get("per_question") or []
    if not per_q:
        return None
    usable = sum(1 for q in per_q if bool(q.get("answer_usable")))
    return usable / len(per_q)


def build_qe_pairing(before_cfg: dict[str, Any], after_cfg: dict[str, Any]) -> dict[str, Any]:
    """Pareia per_question entre `before` (sem QE) e `after` (com QE)."""
    before_by_qid = {q["question_id"]: q for q in before_cfg.get("per_question") or []}
    after_by_qid = {q["question_id"]: q for q in after_cfg.get("per_question") or []}

    only_before = sorted(set(before_by_qid) - set(after_by_qid))
    only_after = sorted(set(after_by_qid) - set(before_by_qid))
    if only_before or only_after:
        raise ValueError(
            f"question_id assimétrico. Só em before: {only_before}; só em after: {only_after}"
        )

    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in PAIRING_BUCKETS}
    for qid in sorted(before_by_qid):
        b = before_by_qid[qid]
        a = after_by_qid[qid]
        b_ok = bool(b.get("answer_usable"))
        a_ok = bool(a.get("answer_usable"))
        entry = _entry(qid, b, a)
        if b_ok and a_ok:
            buckets["stable_pass"].append(entry)
        elif not b_ok and a_ok:
            buckets["saved_by_qe"].append(entry)
        elif b_ok and not a_ok:
            buckets["broken_by_qe"].append(entry)
        else:
            if entry["before_failure_type"] == entry["after_failure_type"]:
                buckets["stable_fail_same_type"].append(entry)
            else:
                buckets["stable_fail_changed_type"].append(entry)

    before_counts = _counts(before_cfg)
    after_counts = _counts(after_cfg)

    saved = len(buckets["saved_by_qe"])
    broken = len(buckets["broken_by_qe"])

    # Critério pré-comprometido (literal):
    # promover SE saved >= 2*broken E delta_retrieval_failures <= 0 E delta_doc_failure <= 0
    promote_ratio = 2
    retrieval_before = before_counts.get(
        "retrieval_document_failure", 0
    ) + before_counts.get("retrieval_passage_failure", 0)
    retrieval_after = after_counts.get(
        "retrieval_document_failure", 0
    ) + after_counts.get("retrieval_passage_failure", 0)
    delta_retrieval = retrieval_after - retrieval_before
    delta_doc = after_counts.get(
        "retrieval_document_failure", 0
    ) - before_counts.get("retrieval_document_failure", 0)

    reasons: list[str] = []
    if saved < promote_ratio * broken:
        reasons.append(f"saved={saved} < {promote_ratio}*broken={promote_ratio*broken}")
    if delta_retrieval > 0:
        reasons.append(f"delta_retrieval_failures=+{delta_retrieval} (piorou)")
    if delta_doc > 0:
        reasons.append(f"delta_doc_failure=+{delta_doc} (piorou)")
    verdict = "promote" if not reasons else "keep_baseline"

    # Estatística do status do rewriter
    qe_status_counts: dict[str, int] = {}
    for q in after_cfg.get("per_question") or []:
        s = str(q.get("query_expansion_status") or "unknown")
        qe_status_counts[s] = qe_status_counts.get(s, 0) + 1

    return {
        "buckets": {n: {"count": len(items), "questions": items} for n, items in buckets.items()},
        "summary": {
            "saved_count": saved,
            "broken_count": broken,
            "net_delta": saved - broken,
            "before_answer_usable_rate": _rate(before_cfg),
            "after_answer_usable_rate": _rate(after_cfg),
            "before_failure_type_counts": before_counts,
            "after_failure_type_counts": after_counts,
            "delta_retrieval_failures": delta_retrieval,
            "delta_doc_failure": delta_doc,
            "qe_status_counts": qe_status_counts,
        },
        "decision_rule": {
            "rule": (
                f"promover QE SE saved >= {promote_ratio}*broken E "
                "delta_retrieval_failures <= 0 E delta_doc_failure <= 0"
            ),
            "saved": saved,
            "broken": broken,
            "delta_retrieval_failures": delta_retrieval,
            "delta_doc_failure": delta_doc,
            "verdict": verdict,
            "reasons": reasons,
        },
    }


def render_qe_pairing_md(par1: dict[str, Any], par2: dict[str, Any]) -> str:
    lines = ["# Pareamento query expansion vs baseline", ""]
    for nome, pairing in [
        ("Par 1 — efeito de QE sobre baseline (sem rerank)", par1),
        ("Par 2 — efeito de QE sobre baseline+rerank", par2),
    ]:
        buckets = pairing.get("buckets") or {}
        summary = pairing.get("summary") or {}
        decision = pairing.get("decision_rule") or {}

        def _rate_str(key: str) -> str:
            value = summary.get(key)
            return "n/d" if value is None else f"{float(value):.3f}"

        lines.append(f"## {nome}")
        lines.append("")
        lines.append("| Bucket | Count |")
        lines.append("|---|---:|")
        for name in PAIRING_BUCKETS:
            lines.append(f"| `{name}` | {(buckets.get(name) or {}).get('count', 0)} |")
        lines.append("")
        lines.append(
            f"`answer_usable_rate`: before {_rate_str('before_answer_usable_rate')} -> "
            f"after {_rate_str('after_answer_usable_rate')} "
            f"(net_delta={summary.get('net_delta', 0):+d})"
        )
        lines.append(
            f"`delta_retrieval_failures`: {summary.get('delta_retrieval_failures', 0):+d}"
        )
        lines.append(
            f"`delta_doc_failure`: {summary.get('delta_doc_failure', 0):+d}"
        )
        qe_status = summary.get("qe_status_counts") or {}
        if qe_status:
            lines.append(f"`qe_status_counts` (na config com QE): {qe_status}")
        lines.append("")

        def _section(title: str, name: str) -> None:
            items = (buckets.get(name) or {}).get("questions") or []
            lines.append(f"### {title} ({len(items)})")
            lines.append("")
            if not items:
                lines.append("_Nenhuma pergunta neste bucket._")
                lines.append("")
                return
            for item in items:
                lines.append(
                    f"- `{item['question_id']}`: {item['before_failure_type']} "
                    f"-> {item['after_failure_type']}"
                )
            lines.append("")

        _section("Salvas pela QE", "saved_by_qe")
        _section("Quebradas pela QE", "broken_by_qe")
        _section("Falhas estáveis com tipo diferente", "stable_fail_changed_type")

        lines.append("### Veredito")
        lines.append("")
        lines.append(f"Regra: {decision.get('rule')}")
        lines.append("")
        lines.append(f"- saved: {decision.get('saved')}")
        lines.append(f"- broken: {decision.get('broken')}")
        lines.append(
            f"- delta_retrieval_failures: {decision.get('delta_retrieval_failures'):+d}"
        )
        lines.append(f"- delta_doc_failure: {decision.get('delta_doc_failure'):+d}")
        lines.append(f"- veredito: **{decision.get('verdict')}**")
        reasons = decision.get("reasons") or []
        if reasons:
            lines.append("- razões:")
            for r in reasons:
                lines.append(f"  - {r}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--per-question",
        type=Path,
        required=True,
        help="per_question.json com 4 configs (rerank x qe)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results/rag-50"),
        help="diretório para gravar query_expansion_pairing.{json,md}",
    )
    args = parser.parse_args()

    payload = json.loads(args.per_question.read_text(encoding="utf-8"))

    # Par 1: rerank=False, qe=False vs rerank=False, qe=True
    par1 = build_qe_pairing(
        _config_by_flags(payload, rerank=False, qe=False),
        _config_by_flags(payload, rerank=False, qe=True),
    )
    # Par 2: rerank=True, qe=False vs rerank=True, qe=True
    par2 = build_qe_pairing(
        _config_by_flags(payload, rerank=True, qe=False),
        _config_by_flags(payload, rerank=True, qe=True),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "query_expansion_pairing.json").write_text(
        json.dumps({"par1_baseline": par1, "par2_with_rerank": par2}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "query_expansion_pairing.md").write_text(
        render_qe_pairing_md(par1, par2), encoding="utf-8"
    )
    print(f"Pareamento QE salvo em {args.output_dir / 'query_expansion_pairing.md'}")
    print(f"  Par 1 (sem rerank): veredito={par1['decision_rule']['verdict']} "
          f"(saved={par1['summary']['saved_count']}, broken={par1['summary']['broken_count']})")
    print(f"  Par 2 (com rerank): veredito={par2['decision_rule']['verdict']} "
          f"(saved={par2['summary']['saved_count']}, broken={par2['summary']['broken_count']})")


if __name__ == "__main__":
    main()
