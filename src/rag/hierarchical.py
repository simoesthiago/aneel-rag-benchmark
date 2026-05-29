"""Estrategia RAG hierarquica."""

from __future__ import annotations

from src.rag.naive import NaiveRAG
from src.rag.retriever import HierarchicalRetriever


class HierarchicalRAG(NaiveRAG):
    def __init__(self, child_retriever, chunks):
        super().__init__(
            HierarchicalRetriever(child_retriever, chunks),
            strategy="hierarchical",
        )
