"""RAG simples sobre um retriever qualquer."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from src.rag.base import BaseRAG, RagResponse
from src.rag.generator import generate_extractive_answer


class NaiveRAG(BaseRAG):
    def __init__(
        self,
        retriever,
        *,
        strategy: str = "dense",
        generator: Callable[[str, list[dict[str, Any]]], Any] | None = None,
    ):
        self.retriever = retriever
        self.strategy = strategy
        self.generator = generator

    def query(self, pergunta: str, top_k: int = 5) -> RagResponse:
        start = perf_counter()
        contexts = self.retriever.retrieve(pergunta, top_k=top_k)
        generated = (
            self.generator(pergunta, contexts)
            if self.generator is not None
            else generate_extractive_answer(contexts)
        )
        answer, cited_indices, generator_status, generator_error = (
            self._normalize_generated(generated)
        )
        latency_ms = (perf_counter() - start) * 1000
        citations = self._select_citations(contexts, cited_indices)
        response = {
            "answer": answer,
            "citations": citations,
            "contexts": contexts,
            "latency_ms": latency_ms,
            "strategy": self.strategy,
        }
        if self.generator is not None:
            response["generator_status"] = generator_status
            response["generator_error"] = generator_error
        return response

    def _normalize_generated(
        self, generated: Any
    ) -> tuple[str, list[int] | None, str, str | None]:
        """Aceita gerador legado `str` e gerador LLM estruturado."""
        if isinstance(generated, dict):
            return (
                str(generated.get("answer") or ""),
                list(generated.get("citations_used") or []),
                str(generated.get("llm_status") or "ok"),
                generated.get("llm_error"),
            )
        return str(generated), None, "extractive", None

    def _select_citations(
        self,
        contexts: list[dict[str, Any]],
        cited_indices: list[int] | None,
    ) -> list[str]:
        """Mapeia índices 1-based do LLM para labels de citação.

        Quando não há gerador estruturado, preserva o comportamento antigo:
        todos os contextos com `citation_label` aparecem em `citations`.
        """
        if cited_indices is None:
            return [
                str(context.get("citation_label"))
                for context in contexts
                if context.get("citation_label")
            ]

        citations: list[str] = []
        for index in cited_indices:
            if not 1 <= int(index) <= len(contexts):
                continue
            label = contexts[int(index) - 1].get("citation_label")
            if label:
                citations.append(str(label))
        return citations
