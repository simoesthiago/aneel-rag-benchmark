"""RAG simples sobre um retriever qualquer."""

from __future__ import annotations

from time import perf_counter

from src.rag.base import BaseRAG, RagResponse
from src.rag.generator import generate_extractive_answer


class NaiveRAG(BaseRAG):
    def __init__(self, retriever, *, strategy: str = "dense"):
        self.retriever = retriever
        self.strategy = strategy

    def query(self, pergunta: str, top_k: int = 5) -> RagResponse:
        start = perf_counter()
        contexts = self.retriever.retrieve(pergunta, top_k=top_k)
        answer = generate_extractive_answer(contexts)
        latency_ms = (perf_counter() - start) * 1000
        citations = [
            context.get("citation_label")
            for context in contexts
            if context.get("citation_label")
        ]
        return {
            "answer": answer,
            "citations": citations,
            "contexts": contexts,
            "latency_ms": latency_ms,
            "strategy": self.strategy,
        }
