"""Helpers para chunking hierarquico parent-child."""

from __future__ import annotations

from typing import Any

from src.chunking.common import build_chunk
from src.chunking.semantic import chunk_article_aware


def chunk_parent_child(document: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Cria chunks de artigo e filhos por paragrafos simples.

    A busca pode mirar os filhos pequenos e a resposta pode usar o contexto pai
    (`parent_chunk_id`) para devolver o artigo inteiro.
    """
    parents = chunk_article_aware(document)
    chunks: list[dict[str, Any]] = []
    for parent in parents:
        parent = dict(parent)
        parent["chunk_strategy"] = "hierarchical"
        parent["chunk_id"] = parent["chunk_id"].replace("article-aware", "hierarchical")
        parent["parent_chunk_id"] = None
        chunks.append(parent)

        paragraphs = [
            part.strip() for part in parent["texto"].split("\n") if part.strip()
        ]
        if len(paragraphs) <= 1:
            continue
        for child_index, paragraph in enumerate(paragraphs):
            chunks.append(
                build_chunk(
                    document,
                    strategy="hierarchical-child",
                    level="paragraph",
                    index=len(chunks),
                    text=paragraph,
                    parent_chunk_id=parent["chunk_id"],
                    secao=parent.get("secao"),
                    artigo=parent.get("artigo"),
                    paragrafo=parent.get("paragrafo"),
                    inciso=parent.get("inciso"),
                    alinea=parent.get("alinea"),
                )
            )
    return chunks
