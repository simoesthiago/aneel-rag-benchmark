"""
extractors/ — Extração de texto plugável por formato de arquivo e formato de saída.

Por que este pacote existe?
---------------------------
O corpus da ANEEL vem em formatos variados: PDF (atos, procedimentos), HTML
(leis), DOCX e XLSX (manuais). Cada um exige um parser diferente — mas o projeto
também compara *formatos de saída* (texto plano vs Markdown) para o benchmark
de RAG. Este é o eixo do benchmark de ingestão.

Eixos do dispatcher:
    formato_arquivo ∈ {"pdf", "html", "docx", "xlsx"}   ← origem
    formato_saida   ∈ {"texto", "markdown"}             ← saída

Mapa de extratores (cada célula é uma ferramenta concreta):

    +------+-------------------+-------------------+
    |      |       texto       |     markdown      |
    +------+-------------------+-------------------+
    | pdf  | pymupdf           | pymupdf4llm       |
    | html | html_parser (bs4) | html2markdown     |
    | docx | python_docx       | mammoth           |
    | xlsx | openpyxl          | pandas_tabulate   |
    +------+-------------------+-------------------+

Contrato de retorno (todos os extratores):
    {
        texto: str,
        num_paginas: int | None,
        qualidade_extracao: float,
        formato_saida: "texto" | "markdown",   → vira coluna metodo_extracao
        extrator: str                          → vira coluna extrator (rastreio)
    }

Como usar:
    from src.ingestion.extractors import extrair_texto

    # Default — texto plano com a ferramenta baseline do formato
    resultado = extrair_texto(pdf_bytes, "pdf")

    # Markdown — usa a ferramenta Markdown do formato (pymupdf4llm para PDF)
    resultado = extrair_texto(pdf_bytes, "pdf", formato_saida="markdown")
"""

from src.ingestion.extractors.html import extrair_texto_html
from src.ingestion.extractors.html2markdown import extrair_texto_html_markdown
from src.ingestion.extractors.mammoth_md import extrair_texto_docx_markdown
from src.ingestion.extractors.office import extrair_texto_docx, extrair_texto_xlsx
from src.ingestion.extractors.pymupdf import extrair_texto_pdf
from src.ingestion.extractors.pymupdf4llm import extrair_texto_pdf_pymupdf4llm
from src.ingestion.extractors.xlsx_markdown import extrair_texto_xlsx_markdown

# Mapa (formato_arquivo, formato_saida) → função extratora.
# Cada formato de arquivo tem uma célula para "texto" e outra para "markdown" —
# simetria total. A coluna `metodo_extracao` no Hub recebe o valor de
# `formato_saida`; a coluna `extrator` recebe o nome da ferramenta real.
_EXTRATORES: dict[str, dict[str, object]] = {
    "pdf": {
        "texto": extrair_texto_pdf,
        "markdown": extrair_texto_pdf_pymupdf4llm,
    },
    "html": {
        "texto": extrair_texto_html,
        "markdown": extrair_texto_html_markdown,
    },
    "docx": {
        "texto": extrair_texto_docx,
        "markdown": extrair_texto_docx_markdown,
    },
    "xlsx": {
        "texto": extrair_texto_xlsx,
        "markdown": extrair_texto_xlsx_markdown,
    },
}

# Formatos de saída válidos — usados na validação do dispatcher e do schema.
FORMATOS_SAIDA_VALIDOS: frozenset[str] = frozenset({"texto", "markdown"})


def extrair_texto(
    conteudo: bytes | str,
    formato_arquivo: str,
    formato_saida: str = "texto",
) -> dict:
    """
    Dispatcher principal — extrai texto de qualquer (formato_arquivo, formato_saida).

    Args:
        conteudo: bytes (PDF, DOCX, XLSX) ou str (HTML)
        formato_arquivo: "pdf", "html", "docx", "xlsx"
        formato_saida: "texto" (default) ou "markdown"

    Returns:
        dict com texto, num_paginas, qualidade_extracao, formato_saida, extrator

    Raises:
        ValueError: formato_arquivo desconhecido ou formato_saida inválido
        TypeError: tipo de `conteudo` incompatível com o formato_arquivo
    """
    formato_arquivo_lower = formato_arquivo.lower()

    if formato_arquivo_lower not in _EXTRATORES:
        raise ValueError(
            f"Formato de arquivo '{formato_arquivo}' não é suportado. "
            f"Formatos válidos: {', '.join(_EXTRATORES)}."
        )

    if formato_saida not in FORMATOS_SAIDA_VALIDOS:
        raise ValueError(
            f"Formato de saída '{formato_saida}' não é válido. "
            f"Valores aceitos: {', '.join(sorted(FORMATOS_SAIDA_VALIDOS))}."
        )

    extrator = _EXTRATORES[formato_arquivo_lower][formato_saida]

    if formato_arquivo_lower == "html":
        # HTML aceita bytes ou str — decodifica bytes com fallback latin-1.
        if isinstance(conteudo, bytes):
            try:
                conteudo = conteudo.decode("utf-8")
            except UnicodeDecodeError:
                conteudo = conteudo.decode("latin-1")
        return extrator(conteudo)

    # PDF, DOCX, XLSX exigem bytes.
    if not isinstance(conteudo, bytes):
        raise TypeError(
            f"Para {formato_arquivo_lower.upper()}, conteudo deve ser bytes."
        )
    return extrator(conteudo)
