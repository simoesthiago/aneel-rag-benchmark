"""Pareamento do filtro de normas revogadas dentro de um `per_question.json`.

Fase 1 do roadmap: medir, com pareamento por `question_id`, o efeito de
descartar chunks de documentos revogados no retrieval. O run gera 2 configs
(rerank@100 sem filtro, rerank@100 com filtro) e este script produz 1
pareamento.

Critério refinado (ROADMAP F1, "factual"): promover o filtro a default SE
`delta_doc_recall >= -0.02` E `hard_broken == 0`, onde *hard_broken* é uma
pergunta que regride (usable -> not usable) E perde `doc_recall` (o filtro
removeu um documento que a resposta precisava). Um *soft break* — regride
mas mantém `doc_recall` — NÃO bloqueia: é ruído de citação do gerador, não
falha do filtro. Racional: o filtro só controla o que entra no pool; sua
única falha legítima é remover um alvo do GT (= queda de doc_recall). O
chão de ruído do gerador (medido re-rodando a config idêntica) flutua ±1-2
perguntas no `usable`, então o sinal estável é `doc_recall`, não o flip.

Uso:
    python scripts/analyze_revogadas_pairing.py \\
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
    "saved_by_filter",
    "broken_by_filter",
    "stable_pass",
    "stable_fail_same_type",
    "stable_fail_changed_type",
]

PROMOTE_MAX_DOC_RECALL_DROP = 0.02

# Tolerância para considerar que doc_recall caiu (evita ruído de float).
DOC_RECALL_DROP_EPS = 1e-9


def _is_hard_break(entry: dict[str, Any]) -> bool:
    """Um break é *hard* se a pergunta regride E perde doc_recall.

    Hard = o filtro removeu um documento que a resposta precisava (falha do
    filtro). Soft = doc_recall intacto; a regressão é ruído de citação do
    gerador, não responsabilidade do filtro.
    """
    before = entry.get("before_doc_recall_at_k")
    after = entry.get("after_doc_recall_at_k")
    if before is None or after is None:
        return True  # sem dado de doc_recall, trate conservadoramente como hard
    return float(after) < float(before) - DOC_RECALL_DROP_EPS


def _config_by_filter(
    payload: dict[str, Any], *, exclude_revogadas: bool
) -> dict[str, Any]:
    """Seleciona a config por flag exclude_revogadas (ambas rerank@100)."""
    for cfg in payload.get("results") or []:
        if bool(cfg.get("exclude_revogadas")) == exclude_revogadas:
            return cfg
    raise ValueError(
        f"Config não encontrada: exclude_revogadas={exclude_revogadas}. "
        "Rode `--mode rag --exclude-revogadas-comparison` para gerar as 2 "
        "configs."
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


def build_revogadas_pairing(
    before_cfg: dict[str, Any], after_cfg: dict[str, Any]
) -> dict[str, Any]:
    """Pareia per_question entre `before` (sem filtro) e `after` (com filtro)."""
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
            buckets["saved_by_filter"].append(entry)
        elif b_ok and not a_ok:
            buckets["broken_by_filter"].append(entry)
        else:
            if entry["before_failure_type"] == entry["after_failure_type"]:
                buckets["stable_fail_same_type"].append(entry)
            else:
                buckets["stable_fail_changed_type"].append(entry)

    before_counts = _counts(before_cfg)
    after_counts = _counts(after_cfg)

    saved = len(buckets["saved_by_filter"])
    broken = len(buckets["broken_by_filter"])
    hard_broken_entries = [e for e in buckets["broken_by_filter"] if _is_hard_break(e)]
    soft_broken_entries = [
        e for e in buckets["broken_by_filter"] if not _is_hard_break(e)
    ]
    hard_broken = len(hard_broken_entries)
    soft_broken = len(soft_broken_entries)

    before_doc_recall = _mean_doc_recall(before_cfg)
    after_doc_recall = _mean_doc_recall(after_cfg)
    delta_doc_recall = (
        None
        if before_doc_recall is None or after_doc_recall is None
        else after_doc_recall - before_doc_recall
    )

    # Critério refinado (ROADMAP F1, factual):
    # promover SE delta_doc_recall >= -0.02 E hard_broken == 0.
    # Soft breaks (regridem mas mantêm doc_recall) são ruído de gerador e
    # não bloqueiam — o filtro só responde por perdas de doc_recall.
    reasons: list[str] = []
    if hard_broken > 0:
        ids = ", ".join(e["question_id"] for e in hard_broken_entries)
        reasons.append(
            f"hard_broken={hard_broken} > 0 (filtro removeu doc do GT: {ids})"
        )
    if delta_doc_recall is not None and delta_doc_recall < -PROMOTE_MAX_DOC_RECALL_DROP:
        reasons.append(
            f"delta_doc_recall={delta_doc_recall:+.3f} < "
            f"-{PROMOTE_MAX_DOC_RECALL_DROP}"
        )
    verdict = "promote" if not reasons else "keep_baseline"

    return {
        "buckets": {
            n: {"count": len(items), "questions": items}
            for n, items in buckets.items()
        },
        "summary": {
            "saved_count": saved,
            "broken_count": broken,
            "hard_broken_count": hard_broken,
            "soft_broken_count": soft_broken,
            "hard_broken_ids": [e["question_id"] for e in hard_broken_entries],
            "soft_broken_ids": [e["question_id"] for e in soft_broken_entries],
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
                "promover filtro de revogadas SE delta_doc_recall >= "
                f"-{PROMOTE_MAX_DOC_RECALL_DROP} E hard_broken == 0 "
                "(soft breaks, com doc_recall intacto, não bloqueiam)"
            ),
            "saved": saved,
            "broken": broken,
            "hard_broken": hard_broken,
            "soft_broken": soft_broken,
            "delta_doc_recall": delta_doc_recall,
            "verdict": verdict,
            "reasons": reasons,
        },
    }


def render_revogadas_pairing_md(pairing: dict[str, Any]) -> str:
    buckets = pairing.get("buckets") or {}
    summary = pairing.get("summary") or {}
    decision = pairing.get("decision_rule") or {}

    def _rate_str(key: str) -> str:
        value = summary.get(key)
        return "n/d" if value is None else f"{float(value):.3f}"

    lines = ["# Pareamento do filtro de revogadas (Fase 1)", ""]
    lines.append("## rerank@100 sem filtro vs com filtro de revogadas")
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

    def _section(title: str, name: str, *, annotate_break: bool = False) -> None:
        items = (buckets.get(name) or {}).get("questions") or []
        lines.append(f"### {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_Nenhuma pergunta neste bucket._")
            lines.append("")
            return
        for item in items:
            tag = ""
            if annotate_break:
                tag = " **[hard]**" if _is_hard_break(item) else " _[soft]_"
            lines.append(
                f"- `{item['question_id']}`: {item['before_failure_type']} "
                f"-> {item['after_failure_type']}{tag}"
            )
        lines.append("")

    _section("Salvas pelo filtro", "saved_by_filter")
    _section("Quebradas pelo filtro", "broken_by_filter", annotate_break=True)
    _section("Falhas estáveis com tipo diferente", "stable_fail_changed_type")

    lines.append("### Veredito")
    lines.append("")
    lines.append(f"Regra: {decision.get('rule')}")
    lines.append("")
    lines.append(
        "_hard break = regride E perde doc_recall (falha do filtro); "
        "soft break = regride mas mantém doc_recall (ruído de gerador)._"
    )
    lines.append("")
    lines.append(f"- saved: {decision.get('saved')}")
    lines.append(
        f"- broken: {decision.get('broken')} "
        f"(hard={decision.get('hard_broken')}, soft={decision.get('soft_broken')})"
    )
    ddr = decision.get("delta_doc_recall")
    lines.append(f"- delta_doc_recall: {'n/d' if ddr is None else f'{ddr:+.3f}'}")
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
        help="per_question.json com 2 configs (rerank@100 ± filtro de revogadas)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results/rag-50"),
        help="diretório para gravar revogadas_pairing.{json,md}",
    )
    args = parser.parse_args()

    payload = json.loads(args.per_question.read_text(encoding="utf-8"))

    pairing = build_revogadas_pairing(
        _config_by_filter(payload, exclude_revogadas=False),
        _config_by_filter(payload, exclude_revogadas=True),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "revogadas_pairing.json").write_text(
        json.dumps(pairing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "revogadas_pairing.md").write_text(
        render_revogadas_pairing_md(pairing), encoding="utf-8"
    )
    print(f"Pareamento de revogadas salvo em {args.output_dir / 'revogadas_pairing.md'}")
    print(
        f"  veredito={pairing['decision_rule']['verdict']} "
        f"(saved={pairing['summary']['saved_count']}, "
        f"broken={pairing['summary']['broken_count']}, "
        f"delta_doc_recall={pairing['summary']['delta_doc_recall']})"
    )


if __name__ == "__main__":
    main()
