"""Pareamento de pool de rerank dentro de um único `per_question.json`.

Fase 2 do roadmap: medir, com rigor pareado, o efeito de aumentar o pool
de candidatos densos do rerank de 50 para 100 no `answer_usable`. O run
gera 3 configs (baseline sem rerank, rerank@50, rerank@100) e este script
produz DOIS pareamentos independentes:

  Par 1 — DECISÃO — efeito isolado do pool:
    rerank@50 vs rerank@100

  Par 2 — CONTEXTO — ganho total do rerank-bom vs sem rerank:
    baseline vs rerank@100

O Par 1 decide a promoção (o Par 2 é informativo). Critério pré-comprometido
(ROADMAP F2): promover pool 100 SE `saved >= 2*broken` E
`delta_doc_recall >= -0.02` (doc_recall@100 − doc_recall@50).

Uso:
    python scripts/analyze_rerank_pool_pairing.py \\
        --per-question data/evaluation/results/rag-50/per_question.json \\
        --output-dir data/evaluation/results/rag-50/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

PAIRING_BUCKETS = [
    "saved_by_pool100",
    "broken_by_pool100",
    "stable_pass",
    "stable_fail_same_type",
    "stable_fail_changed_type",
]

PROMOTE_RATIO = 2
PROMOTE_MAX_DOC_RECALL_DROP = 0.02


def _config_by_pool(
    payload: dict[str, Any], *, rerank: bool, pool: int | None
) -> dict[str, Any]:
    """Seleciona uma config por rerank + candidates_k (pool).

    Para o baseline (rerank=False) o pool é ignorado. Para as configs com
    rerank, `pool` distingue rerank@50 de rerank@100.
    """
    for cfg in payload.get("results") or []:
        if bool(cfg.get("rerank")) != rerank:
            continue
        if not rerank:
            return cfg
        if cfg.get("candidates_k") == pool:
            return cfg
    raise ValueError(
        f"Config não encontrada: rerank={rerank}, candidates_k={pool}. "
        "Rode `--mode rag --rerank-pool-comparison` para gerar as 3 configs."
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


def _mean_doc_recall(cfg: dict[str, Any]) -> float | None:
    values = [
        q.get("doc_recall_at_k")
        for q in cfg.get("per_question") or []
        if q.get("doc_recall_at_k") is not None
    ]
    if not values:
        return None
    return mean(float(v) for v in values)


def build_pool_pairing(
    before_cfg: dict[str, Any], after_cfg: dict[str, Any]
) -> dict[str, Any]:
    """Pareia per_question entre `before` (pool menor) e `after` (pool maior).

    Os buckets `saved_by_pool100`/`broken_by_pool100` referem-se ao efeito de
    `after` sobre `before`, independente dos pools nominais (o nome reflete o
    caso de uso da Fase 2; em Par 2, `before` é o baseline).
    """
    before_by_qid = {q["question_id"]: q for q in before_cfg.get("per_question") or []}
    after_by_qid = {q["question_id"]: q for q in after_cfg.get("per_question") or []}

    only_before = sorted(set(before_by_qid) - set(after_by_qid))
    only_after = sorted(set(after_by_qid) - set(before_by_qid))
    if only_before or only_after:
        raise ValueError(
            f"question_id assimétrico. Só em before: {only_before}; "
            f"só em after: {only_after}"
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
            buckets["saved_by_pool100"].append(entry)
        elif b_ok and not a_ok:
            buckets["broken_by_pool100"].append(entry)
        else:
            if entry["before_failure_type"] == entry["after_failure_type"]:
                buckets["stable_fail_same_type"].append(entry)
            else:
                buckets["stable_fail_changed_type"].append(entry)

    before_counts = _counts(before_cfg)
    after_counts = _counts(after_cfg)

    saved = len(buckets["saved_by_pool100"])
    broken = len(buckets["broken_by_pool100"])

    before_doc_recall = _mean_doc_recall(before_cfg)
    after_doc_recall = _mean_doc_recall(after_cfg)
    delta_doc_recall = (
        None
        if before_doc_recall is None or after_doc_recall is None
        else after_doc_recall - before_doc_recall
    )

    # Critério pré-comprometido (ROADMAP F2):
    # promover SE saved >= 2*broken E delta_doc_recall >= -0.02
    reasons: list[str] = []
    if saved < PROMOTE_RATIO * broken:
        reasons.append(f"saved={saved} < {PROMOTE_RATIO}*broken={PROMOTE_RATIO*broken}")
    if delta_doc_recall is not None and delta_doc_recall < -PROMOTE_MAX_DOC_RECALL_DROP:
        reasons.append(
            f"delta_doc_recall={delta_doc_recall:+.3f} < "
            f"-{PROMOTE_MAX_DOC_RECALL_DROP}"
        )
    verdict = "promote" if not reasons else "keep_pool50"

    return {
        "buckets": {
            n: {"count": len(items), "questions": items}
            for n, items in buckets.items()
        },
        "summary": {
            "saved_count": saved,
            "broken_count": broken,
            "net_delta": saved - broken,
            "before_answer_usable_rate": _rate(before_cfg),
            "after_answer_usable_rate": _rate(after_cfg),
            "before_failure_type_counts": before_counts,
            "after_failure_type_counts": after_counts,
            "before_doc_recall_at_k": before_doc_recall,
            "after_doc_recall_at_k": after_doc_recall,
            "delta_doc_recall": delta_doc_recall,
        },
        "decision_rule": {
            "rule": (
                f"promover pool 100 SE saved >= {PROMOTE_RATIO}*broken E "
                f"delta_doc_recall >= -{PROMOTE_MAX_DOC_RECALL_DROP}"
            ),
            "saved": saved,
            "broken": broken,
            "delta_doc_recall": delta_doc_recall,
            "verdict": verdict,
            "reasons": reasons,
        },
    }


def render_pool_pairing_md(par1: dict[str, Any], par2: dict[str, Any]) -> str:
    lines = ["# Pareamento de pool de rerank (Fase 2)", ""]
    for nome, pairing, decisivo in [
        ("Par 1 — DECISÃO — rerank@50 vs rerank@100", par1, True),
        ("Par 2 — CONTEXTO — baseline vs rerank@100", par2, False),
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
        delta_doc_recall = summary.get("delta_doc_recall")
        delta_str = "n/d" if delta_doc_recall is None else f"{delta_doc_recall:+.3f}"
        lines.append(f"`delta_doc_recall`: {delta_str}")
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

        _section("Salvas pelo pool maior", "saved_by_pool100")
        _section("Quebradas pelo pool maior", "broken_by_pool100")
        _section("Falhas estáveis com tipo diferente", "stable_fail_changed_type")

        lines.append("### Veredito" + (" (decisivo)" if decisivo else " (informativo)"))
        lines.append("")
        lines.append(f"Regra: {decision.get('rule')}")
        lines.append("")
        lines.append(f"- saved: {decision.get('saved')}")
        lines.append(f"- broken: {decision.get('broken')}")
        ddr = decision.get("delta_doc_recall")
        lines.append(
            f"- delta_doc_recall: {'n/d' if ddr is None else f'{ddr:+.3f}'}"
        )
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
        help="per_question.json com 3 configs (baseline + rerank@50 + rerank@100)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results/rag-50"),
        help="diretório para gravar rerank_pool_pairing.{json,md}",
    )
    args = parser.parse_args()

    payload = json.loads(args.per_question.read_text(encoding="utf-8"))

    # Par 1 (decisão): rerank@50 vs rerank@100
    par1 = build_pool_pairing(
        _config_by_pool(payload, rerank=True, pool=50),
        _config_by_pool(payload, rerank=True, pool=100),
    )
    # Par 2 (contexto): baseline vs rerank@100
    par2 = build_pool_pairing(
        _config_by_pool(payload, rerank=False, pool=None),
        _config_by_pool(payload, rerank=True, pool=100),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "rerank_pool_pairing.json").write_text(
        json.dumps(
            {"par1_pool_isolated": par1, "par2_vs_baseline": par2},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output_dir / "rerank_pool_pairing.md").write_text(
        render_pool_pairing_md(par1, par2), encoding="utf-8"
    )
    print(f"Pareamento de pool salvo em {args.output_dir / 'rerank_pool_pairing.md'}")
    print(
        f"  Par 1 (decisão, pool50 vs pool100): "
        f"veredito={par1['decision_rule']['verdict']} "
        f"(saved={par1['summary']['saved_count']}, "
        f"broken={par1['summary']['broken_count']})"
    )
    print(
        f"  Par 2 (contexto, baseline vs pool100): "
        f"saved={par2['summary']['saved_count']}, "
        f"broken={par2['summary']['broken_count']}"
    )


if __name__ == "__main__":
    main()
