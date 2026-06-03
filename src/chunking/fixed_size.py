"""Chunking fixed-size sem dependencias pesadas."""

from __future__ import annotations

from typing import Any

from src.chunking.common import build_chunk, document_text, split_text_by_words


def chunk_fixed_size(
    document: dict[str, Any],
    *,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[dict[str, Any]]:
    """
    Divide `texto_bruto` em chunks por palavras, preservando ordem.

    A unidade e simples de proposito: este e o baseline do benchmark. Chunking
    estrutural e semantico deve ser comparado contra ele, nao misturado nele.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero")
    if overlap < 0:
        raise ValueError("overlap nao pode ser negativo")
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser menor que chunk_size")

    parts = split_text_by_words(
        document_text(document), max_words=chunk_size, overlap=overlap
    )
    if not parts:
        return []

    return [
        build_chunk(
            document,
            strategy="fixed-size",
            level="chunk",
            index=index,
            text=part,
        )
        for index, part in enumerate(parts)
    ]
