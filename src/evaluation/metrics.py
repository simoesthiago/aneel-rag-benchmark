"""Metricas deterministicas e ganchos opcionais para avaliacao LLM."""

from __future__ import annotations

import json
import os
from statistics import mean
from typing import Any, Iterable


def recall_at_k(
    retrieved_ids: Iterable[str], expected_ids: Iterable[str], k: int = 5
) -> float:
    retrieved = set(list(retrieved_ids)[:k])
    expected = set(expected_ids)
    if not expected:
        return 0.0
    return len(retrieved & expected) / len(expected)


def precision_at_k(
    retrieved_ids: Iterable[str], expected_ids: Iterable[str], k: int = 5
) -> float:
    retrieved = list(retrieved_ids)[:k]
    if not retrieved:
        return 0.0
    expected = set(expected_ids)
    return sum(1 for item in retrieved if item in expected) / len(retrieved)


def mrr_at_k(
    retrieved_ids: Iterable[str], expected_ids: Iterable[str], k: int = 5
) -> float:
    expected = set(expected_ids)
    for rank, item in enumerate(list(retrieved_ids)[:k], start=1):
        if item in expected:
            return 1 / rank
    return 0.0


def article_hit_at_k(
    contexts: Iterable[dict[str, Any]],
    expected_article_refs: Iterable[str],
    k: int = 5,
) -> float:
    expected = set(expected_article_refs)
    if not expected:
        return 0.0
    retrieved = {
        f"{context.get('document_id')}::{context.get('artigo')}"
        for context in list(contexts)[:k]
        if context.get("document_id") and context.get("artigo")
    }
    return 1.0 if retrieved & expected else 0.0


def citation_accuracy(citations: Iterable[str], expected_refs: Iterable[str]) -> float:
    expected = [ref for ref in expected_refs if ref]
    if not expected:
        return 0.0
    citation_text = "\n".join(citations)
    hits = sum(1 for ref in expected if ref in citation_text)
    return hits / len(expected)


def status_accuracy(
    contexts: Iterable[dict[str, Any]], expected_status: str | None
) -> float:
    if not expected_status:
        return 0.0
    contexts = list(contexts)
    if not contexts:
        return 0.0
    expected = expected_status.lower()
    hits = sum(
        1
        for context in contexts
        if str(context.get("situacao") or "").lower() == expected
    )
    return hits / len(contexts)


def latency_summary(latencies_ms: Iterable[float]) -> dict[str, float | None]:
    values = sorted(float(value) for value in latencies_ms)
    if not values:
        return {"latency_avg": None, "latency_p95": None}
    p95_index = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
    return {"latency_avg": mean(values), "latency_p95": values[p95_index]}


def optional_llm_metrics(
    *,
    answer: str,
    contexts: list[dict[str, Any]],
    reference: str | None,
) -> dict[str, float | str | None]:
    """
    Executa metricas LLM-as-judge somente quando houver chave configurada.

    A implementacao real pode ser conectada ao Ragas depois; por enquanto o
    contrato explicito evita falha em ambientes zero-custo.
    """
    if not os.environ.get("LLM_API_KEY"):
        return {
            "faithfulness": None,
            "answer_correctness": None,
            "llm_status": "skipped_no_llm_key",
        }
    return _run_openai_judge(answer=answer, contexts=contexts, reference=reference)


def _run_openai_judge(
    *,
    answer: str,
    contexts: list[dict[str, Any]],
    reference: str | None,
) -> dict[str, float | str | None]:
    try:
        from openai import OpenAI
    except ImportError:
        return {
            "faithfulness": None,
            "answer_correctness": None,
            "llm_status": "skipped_missing_openai",
        }

    from src.config.settings import LLM_MODEL, get_llm_api_key

    context_text = "\n\n".join(
        str(context.get("texto") or context.get("text") or "") for context in contexts
    )
    prompt = (
        "Avalie uma resposta RAG regulatoria da ANEEL. "
        "Retorne apenas JSON com chaves faithfulness e answer_correctness, "
        "ambas como numeros entre 0 e 1.\n\n"
        f"Contexto recuperado:\n{context_text}\n\n"
        f"Resposta:\n{answer}\n\n"
        f"Resposta de referencia:\n{reference or ''}"
    )
    try:
        client = OpenAI(api_key=get_llm_api_key())
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Voce e um avaliador factual de sistemas RAG.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return {
            "faithfulness": _coerce_score(parsed.get("faithfulness")),
            "answer_correctness": _coerce_score(parsed.get("answer_correctness")),
            "llm_status": "ok",
        }
    except Exception as exc:
        return {
            "faithfulness": None,
            "answer_correctness": None,
            "llm_status": "error",
            "llm_error": str(exc),
        }


def _coerce_score(value: Any) -> float | None:
    try:
        score = float(value)
    except TypeError, ValueError:
        return None
    return max(0.0, min(1.0, score))


def evaluate_response(
    response: dict[str, Any],
    question: dict[str, Any],
    k: int = 5,
) -> dict[str, Any]:
    contexts = response.get("contexts", [])
    retrieved_doc_ids = [
        context.get("document_id") for context in contexts if context.get("document_id")
    ]
    expected_docs = question.get("expected_document_ids", [])
    expected_articles = question.get("expected_article_refs", [])
    metrics = {
        "recall@5": recall_at_k(retrieved_doc_ids, expected_docs, k=k),
        "precision@5": precision_at_k(retrieved_doc_ids, expected_docs, k=k),
        "mrr@5": mrr_at_k(retrieved_doc_ids, expected_docs, k=k),
        "article_hit@5": article_hit_at_k(contexts, expected_articles, k=k),
        "citation_accuracy": citation_accuracy(
            response.get("citations", []),
            expected_articles,
        ),
        "status_accuracy": status_accuracy(contexts, question.get("expected_status")),
        "latency_ms": response.get("latency_ms"),
    }
    metrics.update(
        optional_llm_metrics(
            answer=response.get("answer", ""),
            contexts=contexts,
            reference=question.get("answer_reference"),
        )
    )
    return metrics
