"""Matching entre chunks recuperados e fontes esperadas do ground truth.

O ground truth identifica cada fonte por `(document_id, section_label)`, onde
section_label é uma string humana como "Art. 1º, §1º, inciso II, alínea a".

Os chunks recuperados carregam:
- `document_id`: identificador do documento (mesma chave que o ground truth)
- `artigo`, `paragrafo`, `inciso`, `alinea`: campos estruturados normalizados
  pelo chunking
- `texto`: o trecho recuperado

A estratégia de matching aqui é simples e auditável:

1. `document_id` precisa ser exato.
2. Construímos uma "assinatura" hierárquica do chunk e da fonte do tipo
   `art1.par1.incII.aliA` e comparamos por prefixo bidirecional — isso captura
   o caso comum em que o chunk é mais amplo (artigo inteiro) ou mais específico
   (parágrafo individual) que a fonte.
3. Quando a fonte ou o chunk não têm estrutura comparável, recorremos ao texto:
   verificamos se os tokens informativos do `support_excerpt` da fonte aparecem
   no `texto` do chunk.

O retorno é a maior nota de `relevance` (1, 2 ou 3) entre as fontes que casam
com o chunk. `0` significa "não relevante".
"""

from __future__ import annotations

import re
from typing import Any, Iterable

import pandas as pd

from src.evaluation.ground_truth import informative_tokens, normalize_text

ARTICLE_RE = re.compile(r"art\.?\s*([0-9]+(?:[\.\-][0-9]+)?)", re.IGNORECASE)
PARAGRAPH_RE = re.compile(
    r"(?:§|paragrafo|paragraph)\s*([0-9]+)", re.IGNORECASE
)
INCISO_RE = re.compile(r"inciso\s+([ivxlcdm0-9]+)", re.IGNORECASE)
ALINEA_RE = re.compile(r"al[ií]nea\s+([a-z])", re.IGNORECASE)
NUMBER_RE = re.compile(r"[0-9]+")

SUPPORT_EXCERPT_TOKEN_THRESHOLD = 0.6


def is_relevant(
    chunk: dict[str, Any],
    relevant_sources: Iterable[dict[str, Any]],
) -> int:
    """Maior nota de relevância (0-3) entre as fontes que casam com o chunk."""
    chunk_doc = chunk.get("document_id")
    if not chunk_doc:
        return 0
    chunk_sig = section_signature_from_chunk(chunk)
    chunk_text_tokens = set(informative_tokens(str(chunk.get("texto") or "")))

    melhor = 0
    for source in relevant_sources:
        if str(source.get("document_id") or "") != str(chunk_doc):
            continue
        nota = _source_grade(source)
        source_sig = section_signature_from_label(
            str(source.get("section_label") or "")
        )
        if _section_matches(chunk_sig, source_sig):
            melhor = max(melhor, nota)
            continue
        if _support_excerpt_matches(source, chunk_text_tokens):
            melhor = max(melhor, nota)
    return melhor


def build_relevance_vector(
    retrieved: Iterable[dict[str, Any]],
    relevant_sources: Iterable[dict[str, Any]],
) -> list[int]:
    """Vetor de relevâncias na ordem do ranking, útil para nDCG."""
    fontes = list(relevant_sources)
    return [is_relevant(chunk, fontes) for chunk in retrieved]


def group_sources(
    relevant_sources: Iterable[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Particiona fontes em grupos `any_of` (OR dentro do grupo).

    Fontes que compartilham um mesmo valor não-vazio de `group` são
    alternativas mutuamente aceitáveis (basta uma ser coberta). Fontes sem
    `group` viram grupos singleton — preservando a semântica AND original
    (cada fonte é obrigatória por si só) para o ground truth não anotado.

    A ordem dos grupos é determinística: grupos nomeados na ordem de primeira
    aparição, depois os singletons na ordem original.
    """
    nomeados: dict[str, list[dict[str, Any]]] = {}
    singletons: list[list[dict[str, Any]]] = []
    for source in relevant_sources:
        chave = source.get("group")
        if chave is None or str(chave).strip() == "":
            singletons.append([source])
        else:
            nomeados.setdefault(str(chave), []).append(source)
    return list(nomeados.values()) + singletons


def document_groups(
    relevant_sources: Iterable[dict[str, Any]],
) -> list[list[str]]:
    """`document_id`s esperados particionados nos mesmos grupos `any_of`."""
    grupos: list[list[str]] = []
    for grupo in group_sources(relevant_sources):
        ids = [str(s.get("document_id")) for s in grupo if s.get("document_id")]
        if ids:
            grupos.append(ids)
    return grupos


def source_coverage(
    retrieved: Iterable[dict[str, Any]],
    relevant_sources: Iterable[dict[str, Any]],
) -> float:
    """Fração de **grupos** de fontes cobertos por pelo menos um chunk.

    Esta é a forma honesta de recall para benchmarks RAG: o que importa é se
    cada fonte do gabarito foi "tocada" no top-k, não o tamanho exato do
    overlap. Múltiplos chunks podem cobrir a mesma fonte.

    Com a semântica `any_of` (ver `group_sources`), um grupo de alternativas
    conta como coberto se **qualquer** de suas fontes for tocada — fontes não
    anotadas viram singletons, recuperando o comportamento AND original.
    """
    chunks = list(retrieved)
    grupos = group_sources(list(relevant_sources))
    if not grupos:
        return 0.0
    cobertos = sum(
        1
        for grupo in grupos
        if any(is_relevant(chunk, [source]) > 0 for source in grupo for chunk in chunks)
    )
    return cobertos / len(grupos)


def section_signature_from_chunk(chunk: dict[str, Any]) -> str:
    """Assinatura hierárquica a partir dos campos estruturados do chunk."""
    parts: list[str] = []
    for field, prefix in (
        ("artigo", "art"),
        ("paragrafo", "par"),
        ("inciso", "inc"),
        ("alinea", "ali"),
    ):
        valor = chunk.get(field)
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            continue
        token = _extract_section_token(str(valor), field)
        if token:
            parts.append(prefix + token)
    return ".".join(parts)


def section_signature_from_label(label: str) -> str:
    """Assinatura hierárquica a partir do `section_label` do ground truth."""
    parts: list[str] = []
    if not label or not label.strip():
        return ""

    art = ARTICLE_RE.search(label)
    if art:
        parts.append("art" + art.group(1))

    par = PARAGRAPH_RE.search(label)
    if par:
        parts.append("par" + par.group(1))

    inc = INCISO_RE.search(label)
    if inc:
        parts.append("inc" + inc.group(1).lower())

    ali = ALINEA_RE.search(label)
    if ali:
        parts.append("ali" + ali.group(1).lower())

    return ".".join(parts)


def _extract_section_token(valor: str, field: str) -> str:
    """Reduz 'Art. 1º' a '1', 'inciso II' a 'ii', 'alinea a' a 'a' etc."""
    valor = valor.strip()
    if field == "alinea":
        match = re.search(r"[a-z]", valor.lower())
        return match.group(0) if match else ""
    if field == "inciso":
        match = re.search(r"[ivxlcdm0-9]+", valor.lower())
        return match.group(0) if match else ""
    match = NUMBER_RE.search(valor)
    return match.group(0) if match else ""


def _section_matches(chunk_sig: str, source_sig: str) -> bool:
    """True se uma assinatura é prefixo da outra."""
    if not source_sig:
        return False
    if not chunk_sig:
        return False
    if chunk_sig == source_sig:
        return True
    return source_sig.startswith(chunk_sig + ".") or chunk_sig.startswith(
        source_sig + "."
    )


def _support_excerpt_matches(
    source: dict[str, Any], chunk_text_tokens: set[str]
) -> bool:
    """Fallback: tokens informativos do support_excerpt aparecem no chunk."""
    excerpt = str(source.get("support_excerpt") or "")
    excerpt_tokens = informative_tokens(excerpt)
    if not excerpt_tokens:
        return False
    hits = sum(1 for token in excerpt_tokens if token in chunk_text_tokens)
    return (hits / len(excerpt_tokens)) >= SUPPORT_EXCERPT_TOKEN_THRESHOLD


def _source_grade(source: dict[str, Any]) -> int:
    """Lê o campo `relevance` da fonte (1, 2 ou 3); default 1 se ausente."""
    try:
        valor = int(source.get("relevance") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(3, valor))


__all__ = [
    "build_relevance_vector",
    "document_groups",
    "group_sources",
    "is_relevant",
    "normalize_text",
    "section_signature_from_chunk",
    "section_signature_from_label",
    "source_coverage",
]
