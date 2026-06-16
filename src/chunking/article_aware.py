"""Chunking article-aware para documentos regulatorios."""

from __future__ import annotations

import re
from typing import Any

from src.chunking.common import build_chunk, document_text, split_text_by_words

MAX_STRUCTURAL_WORDS = 800
STRUCTURAL_OVERLAP = 80
# No fallback (documentos sem artigos), blocos abaixo deste tamanho são fundidos
# com os vizinhos. Sem isso, o markdown — cheio de cabeçalhos/listas/tabelas
# separados por linha em branco — vira uma enxurrada de fragmentos minúsculos.
MIN_MERGE_WORDS = 50

ARTICLE_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"((?:Art\.?|Artigo)\s*\d+[º°o]?(?:-[A-Z])?)"
)
PARAGRAPH_RE = re.compile(r"(§\s*\d+[º°o]?)", re.IGNORECASE)
INCISO_RE = re.compile(r"(?:^|\n|\s)([IVXLCDM]+)\s*[-–]", re.IGNORECASE)
ALINEA_RE = re.compile(r"(?:^|\n|\s)([a-z])\)", re.IGNORECASE)
SECTION_RE = re.compile(
    r"(?im)^\s*("
    r"(?:TITULO|T[IÍ]TULO|CAPITULO|CAP[IÍ]TULO|SECAO|SE[CÇ][AÃ]O|"
    r"MODULO|M[ÓO]DULO|SUBMODULO|SUBM[ÓO]DULO)"
    r"\s+[^\n]+)"
)
# Cabeçalho markdown (ATX): `#`..`######` + espaço + conteúdo. No fallback, serve
# de fronteira de seção para documentos markdown sem artigos — assim o corte
# respeita a estrutura do documento em vez de quebrar em toda linha em branco.
MARKDOWN_HEADING_RE = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+\S")


def chunk_article_aware(document: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Divide documentos por artigo quando possivel.

    Se o texto nao possui marcadores de artigo, usa fallback por paragrafos
    para manter a estrategia operacional em manuais e procedimentos.
    """
    text = document_text(document)
    if not text:
        return []

    article_matches = list(ARTICLE_RE.finditer(text))
    if not article_matches:
        return _fallback_paragraph_chunks(document, text)

    chunks: list[dict[str, Any]] = []
    section_matches = list(SECTION_RE.finditer(text))
    for match_index, match in enumerate(article_matches):
        start = match.start()
        end = (
            article_matches[match_index + 1].start()
            if match_index + 1 < len(article_matches)
            else len(text)
        )
        article_text = text[start:end].strip()
        chunks.extend(
            _build_structural_chunks(
                document,
                strategy="article-aware",
                level="article",
                text=article_text,
                start_index=len(chunks),
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
    blocks = _fallback_blocks(text)
    chunks: list[dict[str, Any]] = []
    for block in blocks:
        secao = _section_title(block)
        chunks.extend(
            _build_structural_chunks(
                document,
                strategy="article-aware",
                level="section" if secao else "paragraph",
                text=block,
                start_index=len(chunks),
                secao=secao,
            )
        )
    return chunks


def _build_structural_chunks(
    document: dict[str, Any],
    *,
    strategy: str,
    level: str,
    text: str,
    start_index: int,
    secao: str | None = None,
    artigo: str | None = None,
    paragrafo: str | None = None,
    inciso: str | None = None,
    alinea: str | None = None,
) -> list[dict[str, Any]]:
    parts = _split_if_long(text)
    return [
        build_chunk(
            document,
            strategy=strategy,
            level=level,
            index=start_index + offset,
            text=part,
            secao=secao,
            artigo=artigo,
            paragrafo=paragrafo,
            inciso=inciso,
            alinea=alinea,
        )
        for offset, part in enumerate(parts)
    ]


def _fallback_blocks(text: str) -> list[str]:
    # Fronteiras de seção: palavras-chave regulatórias (SECTION_RE) E cabeçalhos
    # markdown (MARKDOWN_HEADING_RE). Cortar por elas dá seções coerentes; sem o
    # markdown-aware, docs markdown caíam no corte por linha em branco e
    # estilhaçavam em fragmentos minúsculos.
    boundaries = sorted(
        {
            match.start()
            for match in [
                *SECTION_RE.finditer(text),
                *MARKDOWN_HEADING_RE.finditer(text),
            ]
        }
    )
    if boundaries:
        blocks: list[str] = []
        head = text[: boundaries[0]].strip()
        if head:  # preâmbulo antes da primeira fronteira não pode sumir
            blocks.append(head)
        for index, start in enumerate(boundaries):
            end = (
                boundaries[index + 1]
                if index + 1 < len(boundaries)
                else len(text)
            )
            block = text[start:end].strip()
            if block:
                blocks.append(block)
        if blocks:
            return _merge_small_blocks(blocks)

    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n+", text)
        if part.strip()
    ]
    return _merge_small_blocks(paragraphs or [text.strip()])


def _merge_small_blocks(blocks: list[str]) -> list[str]:
    """Funde blocos consecutivos curtos até `MIN_MERGE_WORDS`, sem passar de
    `MAX_STRUCTURAL_WORDS`. Blocos longos que sobrarem são fatiados depois por
    `_split_if_long`. Mata os fragmentos minúsculos do markdown sem perder texto.
    """
    merged: list[str] = []
    buffer: list[str] = []
    buffer_words = 0
    for block in blocks:
        n = len(block.split())
        # Se anexar estouraria o teto e já há conteúdo acumulado, fecha antes.
        if buffer and buffer_words + n > MAX_STRUCTURAL_WORDS:
            merged.append("\n\n".join(buffer))
            buffer, buffer_words = [], 0
        buffer.append(block)
        buffer_words += n
        if buffer_words >= MIN_MERGE_WORDS:
            merged.append("\n\n".join(buffer))
            buffer, buffer_words = [], 0
    if buffer:  # resto pequeno: anexa ao último bloco para não deixar fragmento
        tail = "\n\n".join(buffer)
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{tail}"
        else:
            merged.append(tail)
    return merged


def _split_if_long(text: str) -> list[str]:
    if len(text.split()) <= MAX_STRUCTURAL_WORDS:
        return [text.strip()]
    return split_text_by_words(
        text, max_words=MAX_STRUCTURAL_WORDS, overlap=STRUCTURAL_OVERLAP
    )


def _section_title(text: str) -> str | None:
    match = SECTION_RE.search(text)
    if not match:
        return None
    return _clean_marker(match.group(1))


def _nearest_section(
    matches: list[re.Match[str]], position: int
) -> str | None:
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
