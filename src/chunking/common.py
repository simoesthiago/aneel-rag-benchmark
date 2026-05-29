"""Helpers compartilhados para gerar chunks do corpus ANEEL."""

from __future__ import annotations

from typing import Any

INHERITED_FIELDS = [
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "situacao",
    "url_original",
    "url_consolidado",
]


def document_text(document: dict[str, Any]) -> str:
    """Retorna o texto bruto de um documento no formato do schema."""
    return str(document.get("texto_bruto") or document.get("texto") or "").strip()


def build_chunk(
    document: dict[str, Any],
    *,
    strategy: str,
    level: str,
    index: int,
    text: str,
    parent_chunk_id: str | None = None,
    secao: str | None = None,
    artigo: str | None = None,
    paragrafo: str | None = None,
    inciso: str | None = None,
    alinea: str | None = None,
) -> dict[str, Any]:
    """Monta um chunk com metadados herdados e campos de citacao."""
    document_id = str(document["id"])
    chunk = {
        "chunk_id": f"{document_id}::{strategy}::{index:04d}",
        "document_id": document_id,
        "parent_chunk_id": parent_chunk_id,
        "chunk_strategy": strategy,
        "chunk_level": level,
        "chunk_index": index,
        "texto": text.strip(),
        "secao": secao,
        "artigo": artigo,
        "paragrafo": paragrafo,
        "inciso": inciso,
        "alinea": alinea,
    }
    for field in INHERITED_FIELDS:
        chunk[field] = document.get(field)
    chunk["citation_label"] = format_citation_label(chunk)
    return chunk


def format_citation_label(chunk: dict[str, Any]) -> str:
    """Cria rotulo curto de citacao a partir de documento e estrutura legal."""
    pieces = [str(chunk.get("titulo") or chunk.get("document_id"))]
    if chunk.get("artigo"):
        pieces.append(str(chunk["artigo"]))
    if chunk.get("paragrafo"):
        pieces.append(str(chunk["paragrafo"]))
    if chunk.get("inciso"):
        pieces.append(f"inciso {chunk['inciso']}")
    if chunk.get("alinea"):
        pieces.append(f"alinea {chunk['alinea']}")
    if len(pieces) == 1 and chunk.get("chunk_index") is not None:
        pieces.append(f"chunk {chunk['chunk_index']}")
    return ", ".join(pieces)
