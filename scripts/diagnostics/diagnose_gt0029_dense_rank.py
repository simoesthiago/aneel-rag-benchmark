"""F2† — rank denso do doc-alvo da gt-0029 (Cohere-free).

Fundamenta a REJEIÇÃO da hipótese "pool 200+ salvaria gt-0029" (ROADMAP, nota
† da Fase 1/2). A pergunta gt-0029 segue como `retrieval_document_failure`
(doc_recall=0) mesmo com rerank pool 100. A dúvida: o doc-alvo está FORA do
pool 100 (aí pool 200 ajudaria) ou DENTRO dele (aí o gargalo é o reranker, e
mais pool só adiciona distratores)?

Este script computa o **rank denso** do doc-alvo no pipeline atual
(text-embedding-3-large + fixed-size + markdown + flat), sem chamar o Cohere
(usa só busca densa + query embeddings em cache), com e sem o filtro de
revogadas. Se o rank <= 100, o doc já é candidato no pool 100 → pool 200+ não
pode ajudar.

Uso:
    .venv/bin/python scripts/diagnostics/diagnose_gt0029_dense_rank.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

QUESTION_ID = "gt-0029"
POOL_PADRAO = 100
PROBE_K = 400  # recupera fundo o suficiente para localizar o doc-alvo


def _expected_document_id(question: dict) -> str:
    fontes = question.get("relevant_sources") or []
    if not fontes:
        raise ValueError(f"{QUESTION_ID} sem relevant_sources no ground truth.")
    return str(fontes[0]["document_id"])


def _dense_rank(
    *, expected_doc: str, query: str, cache: QueryEmbeddingCache, exclude: bool
) -> tuple[int | None, int]:
    common = dict(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        query_cache=cache,
        candidates_k=PROBE_K,
    )
    if exclude:
        common["exclude_situacoes"] = frozenset({"revogada"})
    # Sem reranker => ranking puramente denso.
    chunks = Retriever(**common).retrieve(query, top_k=PROBE_K)
    for chunk in chunks:
        if chunk.get("document_id") == expected_doc:
            return chunk.get("rank"), len(chunks)
    return None, len(chunks)


def main() -> None:
    questions = load_ground_truth_hub()
    question = next(q for q in questions if q.get("question_id") == QUESTION_ID)
    expected_doc = _expected_document_id(question)
    cache = QueryEmbeddingCache()

    print(f"Pergunta: {QUESTION_ID} — {question['question']}")
    print(f"Doc-alvo: {expected_doc}\n")

    for exclude in (False, True):
        rank, n = _dense_rank(
            expected_doc=expected_doc,
            query=question["question"],
            cache=cache,
            exclude=exclude,
        )
        tag = "com filtro de revogadas" if exclude else "sem filtro"
        dentro = rank is not None and rank <= POOL_PADRAO
        veredito = (
            "DENTRO do pool 100 -> pool 200+ NAO ajuda (gargalo no reranker)"
            if dentro
            else "FORA do pool 100 -> reavaliar"
            if rank is not None
            else "doc-alvo nao encontrado nos candidatos densos"
        )
        print(f"[{tag}] rank denso = {rank} (de {n} candidatos) -> {veredito}")


if __name__ == "__main__":
    main()
