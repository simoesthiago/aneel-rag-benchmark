"""Chunking article-aware para documentos regulatorios."""

from __future__ import annotations

import re
from typing import Any

from src.chunking.common import build_chunk, document_text

ARTICLE_RE = re.compile(r"(Art\.?\s*\d+[º°o]?(?:-[A-Z])?)", re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"(§\s*\d+[º°o]?)", re.IGNORECASE)
INCISO_RE = re.compile(r"(?:^|\n|\s)([IVXLCDM]+)\s*[-–]", re.IGNORECASE)
ALINEA_RE = re.compile(r"(?:^|\n|\s)([a-z])\)", re.IGNORECASE)
SECTION_RE = re.compile(
    r"(?im)^\s*((?:TITULO|T[IÍ]TULO|CAPITULO|CAP[IÍ]TULO|SECAO|SE[CÇ][AÃ]O)\s+[^\n]+)"
)


def chunk_article_aware(document: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Divide documentos por artigo quando possivel.

    Se o texto nao possui marcadores de artigo, usa fallback por paragrafos para
    manter a estrategia operacional em manuais e procedimentos menos formais.
    """
    text = document_text(document)
    if not text:
        return []

    article_matches = list(ARTICLE_RE.finditer(text))
    if not article_matches:
        return _fallback_paragraph_chunks(document, text)

    section_matches = list(SECTION_RE.finditer(text))
    chunks: list[dict[str, Any]] = []
    for index, match in enumerate(article_matches):
        start = match.start()
        end = (
            article_matches[index + 1].start()
            if index + 1 < len(article_matches)
            else len(text)
        )
        article_text = text[start:end].strip()
        chunks.append(
            build_chunk(
                document,
                strategy="article-aware",
                level="article",
                index=index,
                text=article_text,
                secao=_nearest_section(section_matches, start),
                artigo=_clean_marker(match.group(1)),
                paragrafo=_first_match(PARAGRAPH_RE, article_text),
                inciso=_first_match(INCISO_RE, article_text),
                alinea=_first_match(ALINEA_RE, article_text),
            )
        )
    return chunks


def _fallback_paragraph_chunks(
    document: dict[str, Any], text: str
) -> list[dict[str, Any]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    return [
        build_chunk(
            document,
            strategy="article-aware",
            level="paragraph",
            index=index,
            text=paragraph,
        )
        for index, paragraph in enumerate(paragraphs)
    ]


def _nearest_section(matches: list[re.Match[str]], position: int) -> str | None:
    current: str | None = None
    for match in matches:
        if match.start() > position:
            break
        current = " ".join(match.group(1).split())
    return current


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return _clean_marker(match.group(1))


def _clean_marker(value: str) -> str:
    return " ".join(value.strip().split())
