"""Auditoria consolidada de fragmentação H12 sem alterar artefatos.

O script cruza três fontes já existentes:

1. `per_question.json` do run oficial de retrieval.
2. Ground truth local versionado no repositório.
3. `metadata.parquet` das vector stores publicadas no Hub.

Ele não publica chunks, não gera embeddings e não chama LLM/reranker. A saída
serve para explicar por que `article-aware` e `hierarchical-child` perdem em
granularidade, e para separar retrieval puro de qualidade RAG final.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.evaluation.ground_truth import load_ground_truth_jsonl  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import (  # noqa: E402
    METADATA_FILENAME,
    PARENTS_FILENAME,
)

PROVIDER = "openai"
MODEL = "text-embedding-3-large"
STRATEGIES = ("fixed-size", "article-aware", "hierarchical-child")
METODOS = ("markdown", "texto")
TINY_WORDS = 10
SMALL_WORDS = 30
SAMPLE_SIZE = 5

RETRIEVAL_PER_QUESTION_PATH = Path(
    "data/evaluation/runs/retrieval/"
    "20260614T161535Z-18d8e21/per_question.json"
)
GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")
RETRIEVAL_MATRIX_PATH = Path("data/evaluation/report/tables/retrieval_matrix.csv")
RAG_FINALISTS_PATH = Path("data/evaluation/report/tables/rag_finalists.csv")
OUT_JSON = Path(
    "data/evaluation/results/diagnostic/chunking_fragmentation_audit.json"
)
OUT_MD = Path(
    "data/evaluation/results/diagnostic/chunking_fragmentation_audit.md"
)


def main() -> None:
    """Gera JSON e Markdown da auditoria consolidada."""
    questions = load_ground_truth_jsonl(GT_PATH)
    question_by_id = {row["question_id"]: row for row in questions}
    per_question = _read_json(RETRIEVAL_PER_QUESTION_PATH)

    shape_rows = _build_shape_rows()
    gap_rows = _build_gap_rows(per_question, question_by_id)
    noise_rows = _build_noise_rows(shape_rows)
    narrative = _build_text_vs_markdown_narrative()

    payload = {
        "inputs": {
            "retrieval_per_question": str(RETRIEVAL_PER_QUESTION_PATH),
            "ground_truth": str(GT_PATH),
            "metadata_source": f"{HF_DATASET_REPO}:{MODEL}",
        },
        "shape_summary": [
            row["summary"] for row in shape_rows if row["kind"] == "chunks"
        ],
        "shape_summary_with_parents": [row["summary"] for row in shape_rows],
        "markdown_noise_counts": noise_rows,
        "doc_hit_without_passage_hit": gap_rows,
        "text_vs_markdown": narrative,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_metadata(strategy: str, metodo: str, filename: str) -> pd.DataFrame:
    prefix = hub_prefix(
        provider=PROVIDER,
        model=MODEL,
        chunk_strategy=strategy,
        metodo_extracao=metodo,
    )
    local = hf_hub_download(
        repo_id=HF_DATASET_REPO,
        filename=f"{prefix}/{filename}",
        repo_type="dataset",
    )
    return pd.read_parquet(local, engine="pyarrow")


def _word_count(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.split().map(len)


def _shape_summary(
    df: pd.DataFrame,
    *,
    strategy: str,
    metodo: str,
    kind: str,
) -> dict[str, Any]:
    words = _word_count(df["texto"])
    total = int(len(words))
    tiny = int((words < TINY_WORDS).sum())
    small = int((words < SMALL_WORDS).sum())
    return {
        "strategy": strategy,
        "metodo_extracao": metodo,
        "kind": kind,
        "n_chunks": total,
        "tiny_lt_10": tiny,
        "tiny_lt_10_pct": round(tiny / total, 4) if total else 0.0,
        "small_lt_30": small,
        "small_lt_30_pct": round(small / total, 4) if total else 0.0,
        "p50_words": int(words.quantile(0.5)) if total else 0,
        "p95_words": int(words.quantile(0.95)) if total else 0,
        "examples": _tiny_examples(df, words),
    }


def _tiny_examples(df: pd.DataFrame, words: pd.Series) -> list[dict[str, Any]]:
    sample = df.assign(n_words=words)
    sample = sample[sample["n_words"] < SMALL_WORDS]
    if sample.empty:
        return []
    sample = sample.sort_values(["n_words", "chunk_id"]).head(SAMPLE_SIZE)
    return [
        {
            "chunk_id": str(row.get("chunk_id") or ""),
            "document_id": str(row.get("document_id") or ""),
            "n_words": int(row["n_words"]),
            "noise_kind": _classify_noise(str(row.get("texto") or "")),
            "texto": _preview(row.get("texto")),
        }
        for _, row in sample.iterrows()
    ]


def _build_shape_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy in STRATEGIES:
        for metodo in METODOS:
            df = _read_metadata(strategy, metodo, METADATA_FILENAME)
            rows.append(
                {
                    "strategy": strategy,
                    "metodo_extracao": metodo,
                    "kind": "chunks",
                    "df": df,
                    "summary": _shape_summary(
                        df,
                        strategy=strategy,
                        metodo=metodo,
                        kind="chunks",
                    ),
                }
            )
            if strategy == "hierarchical-child":
                parents = _read_metadata(strategy, metodo, PARENTS_FILENAME)
                rows.append(
                    {
                        "strategy": strategy,
                        "metodo_extracao": metodo,
                        "kind": "parents",
                        "df": parents,
                        "summary": _shape_summary(
                            parents,
                            strategy=strategy,
                            metodo=metodo,
                            kind="parents",
                        ),
                    }
                )
    return rows


def _build_noise_rows(shape_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in shape_rows:
        if row["metodo_extracao"] != "markdown" or row["kind"] != "chunks":
            continue
        df = row["df"]
        words = _word_count(df["texto"])
        tiny = df.loc[words < SMALL_WORDS].copy()
        counts = Counter(
            _classify_noise(str(text or "")) for text in tiny["texto"].tolist()
        )
        rows.append(
            {
                "strategy": row["strategy"],
                "metodo_extracao": row["metodo_extracao"],
                "n_tiny_lt_30": int(len(tiny)),
                "noise_counts": dict(sorted(counts.items())),
            }
        )
    return rows


def _classify_noise(text: str) -> str:
    stripped = " ".join(str(text or "").strip().split())
    lower = stripped.lower()
    if "picture" in lower and "omitted" in lower:
        return "marcador_imagem_omitida"
    if "|" in stripped and ("---" in stripped or "<br>" in lower):
        return "tabela_markdown"
    if re.search(r"(?i)\bp[áa]g(?:ina)?\.?\s*\d+\b", stripped):
        return "numero_pagina"
    if re.match(r"^\**\s*\d+\s*/\s*\d+\s*\**$", stripped):
        return "numero_pagina"
    if "http://" in lower or "https://" in lower or "www." in lower:
        return "url_footer"
    if re.match(r"^(?:#+\s*)?(?:\*\*)?\d+(?:\.\d+)+", stripped):
        return "cabecalho_isolado"
    if re.match(r"^(?:#+\s*)?(?:\*\*)?[A-ZÁÉÍÓÚÇ ]{4,}", stripped):
        return "cabecalho_isolado"
    if re.match(r"(?i)^art\.?\s*\d+[º°o]?(?:-[a-z])?\s+(?:na|no|da|do)\b", stripped):
        return "fragmento_referencia_cruzada"
    if re.match(r"^-?\s*\(?[a-z0-9]+\)?\s*[-–)]", stripped):
        return "item_lista_curto"
    return "outro"


def _build_gap_rows(
    per_question: dict[str, Any],
    question_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in per_question.get("results", []):
        strategy = str(config.get("chunk_strategy") or "")
        if strategy not in {"article-aware", "hierarchical-child"}:
            continue
        gap_qids: list[dict[str, Any]] = []
        for item in config.get("per_question", []):
            if item.get("doc_recall_at_k") == 1.0 and item.get("recall_at_k") == 0.0:
                qid = str(item.get("question_id"))
                question = question_by_id.get(qid, {})
                gap_qids.append(
                    {
                        "question_id": qid,
                        "question": question.get("question"),
                        "tipo": question.get("tipo"),
                        "subtipo": question.get("subtipo"),
                    }
                )
        if gap_qids:
            rows.append(
                {
                    "label": _config_label(config),
                    "model": config.get("model"),
                    "strategy": strategy,
                    "metodo_extracao": config.get("metodo_extracao"),
                    "mode": config.get("mode"),
                    "rerank": bool(config.get("rerank")),
                    "count": len(gap_qids),
                    "questions": gap_qids,
                }
            )
    return rows


def _config_label(config: dict[str, Any]) -> str:
    suffix = "+rerank" if bool(config.get("rerank")) else ""
    return (
        f"{config.get('model')}|{config.get('chunk_strategy')}|"
        f"{config.get('metodo_extracao')}|{config.get('mode')}{suffix}"
    )


def _build_text_vs_markdown_narrative() -> dict[str, Any]:
    retrieval = pd.read_csv(RETRIEVAL_MATRIX_PATH)
    rag = pd.read_csv(RAG_FINALISTS_PATH)

    retrieval_top = retrieval[
        (retrieval["model"] == MODEL)
        & (retrieval["chunk_strategy"] == "fixed-size")
        & (retrieval["mode"] == "flat")
        & (retrieval["rerank"] == True)  # noqa: E712
    ].sort_values("metodo_extracao")
    rag_top = rag[
        (rag["model"] == MODEL)
        & (rag["rerank"] == True)  # noqa: E712
    ].sort_values("metodo_extracao")

    return {
        "retrieval_fixed_size_rerank": retrieval_top.to_dict("records"),
        "rag_fixed_size_rerank": rag_top.to_dict("records"),
        "interpretation": (
            "Markdown lidera doc_recall no retrieval puro, mas texto vence "
            "o gate RAG por citation_accuracy e answer_usable_rate. A auditoria "
            "deve tratar essas conclusões como métricas diferentes."
        ),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Auditoria H12 — fragmentação de chunks",
        "",
        "Esta auditoria não reconstrói chunks, vectorstores ou embeddings.",
        "",
        "## Shape dos chunks",
        "",
        "| strategy | método | kind | n | <10 | <30 | p50 | p95 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["shape_summary_with_parents"]:
        lines.append(
            "| {strategy} | {metodo_extracao} | {kind} | {n_chunks} | "
            "{tiny_lt_10} ({tiny_lt_10_pct:.1%}) | "
            "{small_lt_30} ({small_lt_30_pct:.1%}) | "
            "{p50_words} | {p95_words} |".format(**row)
        )

    lines.extend(["", "## Ruído markdown em chunks <30 palavras", ""])
    for row in payload["markdown_noise_counts"]:
        lines.append(f"### {row['strategy']}")
        for kind, count in row["noise_counts"].items():
            lines.append(f"- `{kind}`: {count}")
        lines.append("")

    lines.extend(["## Exemplos tiny", ""])
    for row in payload["shape_summary"]:
        examples = row.get("examples") or []
        if not examples:
            continue
        lines.append(f"### {row['strategy']} / {row['metodo_extracao']}")
        for example in examples:
            lines.append(
                f"- `{example['chunk_id']}` ({example['n_words']} palavras, "
                f"{example['noise_kind']}): {example['texto']}"
            )
        lines.append("")

    lines.extend(
        [
            "## Documento certo sem trecho certo",
            "",
            "Casos em que `doc_recall_at_k = 1` e `recall_at_k = 0`.",
            "",
        ]
    )
    for row in payload["doc_hit_without_passage_hit"]:
        qids = ", ".join(q["question_id"] for q in row["questions"])
        lines.append(f"- `{row['label']}`: {row['count']} perguntas ({qids})")

    lines.extend(["", "## Texto vs markdown", ""])
    lines.append(payload["text_vs_markdown"]["interpretation"])
    lines.append("")
    lines.append("### Retrieval puro — fixed-size + rerank")
    lines.append("")
    lines.append("| método | recall | doc_recall | MRR | nDCG |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in payload["text_vs_markdown"]["retrieval_fixed_size_rerank"]:
        lines.append(
            f"| {row['metodo_extracao']} | {row['recall_at_k']:.3f} | "
            f"{row['doc_recall_at_k']:.3f} | {row['mrr_at_k']:.3f} | "
            f"{row['ndcg_at_k']:.3f} |"
        )
    lines.append("")
    lines.append("### RAG finalistas — fixed-size + rerank")
    lines.append("")
    lines.append("| método | usable | citation | correctness | doc_recall |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in payload["text_vs_markdown"]["rag_fixed_size_rerank"]:
        lines.append(
            f"| {row['metodo_extracao']} | "
            f"{row['answer_usable_rate']:.3f} | "
            f"{row['citation_accuracy_avg']:.3f} | "
            f"{row['answer_correctness_avg']:.3f} | "
            f"{row['doc_recall_at_k']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _preview(value: object, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


if __name__ == "__main__":
    main()
