"""Metricas deterministicas e ganchos opcionais para avaliacao LLM."""

from __future__ import annotations

import json
import math
import os
from statistics import mean
from typing import Any, Iterable


def recall_at_k(
    retrieved_ids: Iterable[str], expected_ids: Iterable[str], k: int = 5
) -> float:
    """Recall genérico por id (chunk_id, document_id ou qualquer chave).

    No benchmark de retrieval atual essa métrica é alimentada com chunks
    casados via `source_coverage` (chunk casa fonte por estrutura
    hierárquica ou cobertura de support_excerpt). Logo, é semanticamente
    equivalente a **passage_recall_at_k** — mede se o trecho relevante foi
    recuperado, não apenas se o documento certo apareceu.

    Para medir "achou o documento certo independente do trecho", use
    `doc_recall_at_k`.
    """
    retrieved = set(list(retrieved_ids)[:k])
    expected = set(expected_ids)
    if not expected:
        return 0.0
    return len(retrieved & expected) / len(expected)


def doc_recall_at_k(
    contexts: Iterable[dict[str, Any]],
    expected_document_ids: Iterable[str],
    k: int = 10,
) -> float:
    """Fração de `document_id`s esperados cobertos por algum chunk no top-k.

    Diferente de `recall_at_k` (que mede passage-level via matching de
    section/excerpt), esta métrica olha apenas o `document_id` dos chunks
    retornados. Se a melhor config tem `doc_recall` alto mas `recall` baixo,
    significa que o retriever encontra o documento certo mas erra o trecho
    específico — sinal de problema de chunking/granularidade, não de
    retrieval por se.

    Args:
        contexts: chunks devolvidos pelo Retriever, com campo `document_id`
        expected_document_ids: ids únicos dos documentos esperados (do GT)
        k: top-k a considerar
    """
    expected = {str(doc_id) for doc_id in expected_document_ids if doc_id}
    if not expected:
        return 0.0
    top_k = list(contexts)[:k]
    retrieved_docs = {
        str(ctx.get("document_id")) for ctx in top_k if ctx.get("document_id")
    }
    return len(retrieved_docs & expected) / len(expected)


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


def ndcg_at_k(relevances: Iterable[int], k: int = 10) -> float:
    """nDCG@k a partir de um vetor de relevâncias na ordem do ranking.

    `relevances[i]` é a nota de relevância (0-3) do chunk recuperado na
    posição i. Use `src.evaluation.matching.build_relevance_vector` para
    produzir esse vetor a partir de chunks + relevant_sources.

    DCG@k = sum_i rel_i / log2(i + 2)  (i começa em 0)
    IDCG@k = DCG@k com `relevances` ordenado decrescente
    nDCG@k = DCG@k / IDCG@k

    Retorna 0.0 se não houver nenhum item relevante (IDCG = 0).
    """
    vetor = [max(0, int(value)) for value in list(relevances)[:k]]
    dcg = sum(rel / math.log2(index + 2) for index, rel in enumerate(vetor))
    ideal = sorted(vetor, reverse=True)
    idcg = sum(rel / math.log2(index + 2) for index, rel in enumerate(ideal))
    if idcg == 0:
        return 0.0
    return dcg / idcg


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


def citation_accuracy(
    citations: Iterable[str],
    expected_refs: Iterable[str],
) -> float:
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
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")):
        return {
            "faithfulness": None,
            "answer_correctness": None,
            "llm_status": "skipped_no_llm_key",
        }
    return _run_openai_judge(
        answer=answer,
        contexts=contexts,
        reference=reference,
    )


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

    from src.config.settings import LLM_JUDGE_MODEL, get_llm_api_key

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
            model=LLM_JUDGE_MODEL,
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
    except (TypeError, ValueError):
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
        f"recall@{k}": recall_at_k(retrieved_doc_ids, expected_docs, k=k),
        f"precision@{k}": precision_at_k(
            retrieved_doc_ids,
            expected_docs,
            k=k,
        ),
        f"mrr@{k}": mrr_at_k(retrieved_doc_ids, expected_docs, k=k),
        f"article_hit@{k}": article_hit_at_k(
            contexts,
            expected_articles,
            k=k,
        ),
        "citation_accuracy": citation_accuracy(
            response.get("citations", []),
            expected_articles,
        ),
        "status_accuracy": status_accuracy(
            contexts,
            question.get("expected_status"),
        ),
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
