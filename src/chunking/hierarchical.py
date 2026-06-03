"""Helpers para chunking hierarquico parent-child."""

from __future__ import annotations

from typing import Any

from src.chunking.article_aware import chunk_article_aware
from src.chunking.common import build_chunk, split_text_by_words


def chunk_parent_child(
    document: dict[str, Any],
    *,
    child_size: int = 300,
    overlap: int = 40,
) -> list[dict[str, Any]]:
    """
    Cria chunks pai estruturais e filhos menores para retrieval.

    A busca pode mirar os filhos pequenos e a resposta pode usar o contexto pai
    (`parent_chunk_id`) para devolver o artigo inteiro.
    """
    structural_chunks = chunk_article_aware(document)
    chunks: list[dict[str, Any]] = []
    child_index = 0

    for parent_index, source in enumerate(structural_chunks):
        parent = build_chunk(
            document,
            strategy="hierarchical",
            level=source["chunk_level"],
            index=parent_index,
            text=source["texto"],
            secao=source.get("secao"),
            artigo=source.get("artigo"),
            paragrafo=source.get("paragrafo"),
            inciso=source.get("inciso"),
            alinea=source.get("alinea"),
        )
        chunks.append(parent)

        for child_text in split_text_by_words(
            parent["texto"], max_words=child_size, overlap=overlap
        ):
            chunks.append(
                build_chunk(
                    document,
                    strategy="hierarchical-child",
                    level="paragraph",
                    index=child_index,
                    text=child_text,
                    parent_chunk_id=parent["chunk_id"],
                    secao=parent.get("secao"),
                    artigo=parent.get("artigo"),
                    paragrafo=parent.get("paragrafo"),
                    inciso=parent.get("inciso"),
                    alinea=parent.get("alinea"),
                )
            )
            child_index += 1
    return chunks
