"""
extractors/ — Extração de texto plugável por formato e estratégia.

Por que este pacote existe?
---------------------------
O corpus da ANEEL vem em formatos variados: PDF (atos, procedimentos), HTML
(leis), DOCX e XLSX (manuais). Cada formato exige um parser diferente — mas o
projeto também compara *estratégias* de extração para o mesmo formato (ex.: PDF
via PyMuPDF vs Docling). Isso é o benchmark de ingestão.

O dispatcher `extrair_texto(conteudo, formato, estrategia)` esconde dessa escolha
dos scrapers: eles só dizem "extraia este PDF com a estratégia X" e recebem de
volta texto + metadados num contrato uniforme.

Contrato de retorno (todos os extratores):
    {texto: str, num_paginas: int|None, qualidade_extracao: float, metodo: str}

O campo `metodo` vira `metodo_extracao` no schema — é o que distingue as linhas
de um mesmo documento extraído por estratégias diferentes (ver docs/schema.md).

Como usar:
    from src.ingestion.extractors import extrair_texto

    resultado = extrair_texto(pdf_bytes, "pdf")                           # PyMuPDF (default)
    resultado = extrair_texto(pdf_bytes, "pdf", estrategia="pymupdf4llm") # Markdown
"""

from src.ingestion.extractors.html import extrair_texto_html
from src.ingestion.extractors.office import extrair_texto_docx, extrair_texto_xlsx
from src.ingestion.extractors.pymupdf import extrair_texto_pdf
from src.ingestion.extractors.pymupdf4llm import extrair_texto_pdf_pymupdf4llm

# Mapa (formato, estratégia) → extrator. A primeira estratégia de cada formato é
# o default usado quando o chamador não especifica `estrategia`.
_EXTRATORES: dict[str, dict[str, object]] = {
    "pdf": {
        "pymupdf": extrair_texto_pdf,
        "pymupdf4llm": extrair_texto_pdf_pymupdf4llm,
    },
    "html": {
        "beautifulsoup": extrair_texto_html,
    },
    "docx": {
        "python_docx": extrair_texto_docx,
    },
    "xlsx": {
        "openpyxl": extrair_texto_xlsx,
    },
}

# Estratégia default por formato (primeira registrada).
_ESTRATEGIA_DEFAULT: dict[str, str] = {
    fmt: next(iter(estrategias)) for fmt, estrategias in _EXTRATORES.items()
}


def extrair_texto(
    conteudo: bytes | str,
    formato: str,
    estrategia: str | None = None,
) -> dict:
    """
    Dispatcher principal — extrai texto de qualquer formato/estratégia suportado.

    Este é o ponto de entrada que os scrapers usam. Delega para o extrator
    específico de cada (formato, estratégia).

    Args:
        conteudo: bytes (PDF, DOCX, XLSX) ou str (HTML)
        formato: "pdf", "html", "docx", "xlsx"
        estrategia: nome da estratégia. Se None, usa a default do formato.
            PDF aceita "pymupdf" (default) e "docling". HTML/DOCX/XLSX têm
            estratégia única.

    Returns:
        dict com texto, num_paginas, qualidade_extracao, metodo

    Raises:
        ValueError: formato desconhecido ou estratégia inválida para o formato
        TypeError: tipo de `conteudo` incompatível com o formato
    """
    formato_lower = formato.lower()

    if formato_lower not in _EXTRATORES:
        raise ValueError(
            f"Formato '{formato}' não é suportado. "
            f"Formatos válidos: {', '.join(_EXTRATORES)}."
        )

    estrategias = _EXTRATORES[formato_lower]
    estrategia = estrategia or _ESTRATEGIA_DEFAULT[formato_lower]
    if estrategia not in estrategias:
        raise ValueError(
            f"Estratégia '{estrategia}' não é válida para formato '{formato_lower}'. "
            f"Estratégias válidas: {', '.join(estrategias)}."
        )

    extrator = estrategias[estrategia]

    if formato_lower == "html":
        # HTML aceita bytes ou str — decodifica bytes com fallback latin-1.
        if isinstance(conteudo, bytes):
            try:
                conteudo = conteudo.decode("utf-8")
            except UnicodeDecodeError:
                conteudo = conteudo.decode("latin-1")
        return extrator(conteudo)

    # PDF, DOCX, XLSX exigem bytes.
    if not isinstance(conteudo, bytes):
        raise TypeError(f"Para {formato_lower.upper()}, conteudo deve ser bytes.")
    return extrator(conteudo)
