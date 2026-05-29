"""Estrategia dense FAISS para RAG semantico."""

from __future__ import annotations

from src.embeddings.embedder import build_embedder
from src.rag.naive import NaiveRAG
from src.rag.retriever import DenseRetriever
from src.vectorstore.store import FaissVectorStore


def build_semantic_rag(chunks, embedder=None) -> NaiveRAG:
    embedder = embedder or build_embedder()
    sample = embedder.embed_query("dimensao")
    retriever = DenseRetriever(
        chunks, embedder, FaissVectorStore(dimension=len(sample))
    )
    return NaiveRAG(retriever, strategy="dense_faiss")
