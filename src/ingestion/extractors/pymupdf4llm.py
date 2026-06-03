"""
pymupdf4llm.py — Extração de PDF em Markdown via PyMuPDF4LLM.

Segunda estratégia do benchmark de extração. Mesma biblioteca do baseline
(PyMuPDF/fitz), mas exporta Markdown estruturado em vez de texto plano —
preserva hierarquia de títulos, listas e tabelas. Sem modelos de ML,
sem dependência de torch, sem overhead de memória.

Diferença em relação ao baseline `pymupdf`:
    pymupdf    → texto plano, páginas separadas por \\n\\n
    pymupdf4llm → Markdown estruturado (# Título, ## Seção, | tabela |)

O Markdown melhora o chunking da Camada 2 (os separadores de seção são
sinais naturais) e facilita a extração de artigos e incisos.
"""

import io


def extrair_texto_pdf_pymupdf4llm(conteudo: bytes) -> dict:
    """
    Extrai texto de um PDF como Markdown usando pymupdf4llm.

    Totalmente em memória — não salva em disco.

    Args:
        conteudo: bytes do arquivo PDF

    Returns:
        dict com:
            texto (str): conteúdo em Markdown
            num_paginas (int): total de páginas do PDF
            qualidade_extracao (float): 0.0 a 1.0 (fração de páginas com texto)
            formato_saida (str): sempre "markdown"
            extrator (str): sempre "pymupdf4llm"
    """
    try:
        import pymupdf4llm
        import fitz
    except ImportError:
        raise RuntimeError(
            "pymupdf4llm não está instalado. "
            "Instale com: pip install pymupdf4llm"
        )

    pdf = fitz.open(stream=io.BytesIO(conteudo), filetype="pdf")
    num_paginas = len(pdf)

    # Calcula qualidade com o documento ainda aberto
    paginas_com_texto = sum(
        1 for p in pdf if len(p.get_text().strip()) > 100
    )
    qualidade = round(paginas_com_texto / num_paginas, 2) if num_paginas > 0 else 0.0

    # to_markdown recebe o fitz.Document aberto (não BytesIO)
    texto = pymupdf4llm.to_markdown(pdf, show_progress=False)
    pdf.close()

    return {
        "texto": texto,
        "num_paginas": num_paginas,
        "qualidade_extracao": qualidade,
        "formato_saida": "markdown",
        "extrator": "pymupdf4llm",
    }
