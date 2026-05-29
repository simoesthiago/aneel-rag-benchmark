"""Runner simples de benchmark para estrategias RAG."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.evaluation.metrics import evaluate_response, latency_summary


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("questions", []))
    return list(data)


def run_benchmark(
    rag, questions: list[dict[str, Any]], *, top_k: int = 5
) -> dict[str, Any]:
    rows = []
    for question in questions:
        response = rag.query(question["pergunta"], top_k=top_k)
        row = {
            "id": question["id"],
            "strategy": response["strategy"],
            **evaluate_response(response, question, k=top_k),
        }
        rows.append(row)

    latencies = [row["latency_ms"] for row in rows if row.get("latency_ms") is not None]
    return {
        "strategy": getattr(rag, "strategy", "unknown"),
        "num_questions": len(rows),
        "rows": rows,
        **latency_summary(latencies),
    }
