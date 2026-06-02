"""
pymupdf.py — Extração de texto de PDF via PyMuPDF (fitz).

Estratégia baseline do benchmark de extração. Rápida, sem dependências de ML,
funciona bem em PDFs nativos (texto selecionável). Para PDFs escaneados ou com
layout complexo (tabelas), a estratégia `docling` tende a extrair melhor — a
comparação é justamente o objeto do benchmark (ver docs/schema.md).
"""

import io


def extrair_texto_pdf(conteudo: bytes) -> dict:
    """
    Extrai texto de um PDF usando PyMuPDF (fitz).

    Processa o PDF inteiramente em memória — NUNCA salva em disco.
    Isso é fundamental: o projeto opera com a premissa de que dados brutos
    não são persistidos em disco no repo (processamento em memória → HF Hub).

    Calcula `qualidade_extracao` como a fração de páginas que têm texto
    substancial (>100 chars). Páginas com menos que isso provavelmente
    são escaneadas (imagem) e precisariam de OCR.

    Args:
        conteudo: bytes do arquivo PDF

    Returns:
        dict com:
            texto (str): texto completo concatenado (páginas separadas por \\n\\n)
            num_paginas (int): total de páginas do PDF
            qualidade_extracao (float): 0.0 a 1.0, fração de páginas com texto
            metodo (str): sempre "pymupdf"
    """
    # Import aqui porque PyMuPDF não instala em todos os ambientes
    # (exige compilação nativa — funciona no Colab mas pode falhar local)
    try:
        import fitz  # PyMuPDF é importado como "fitz" por razões históricas
    except ImportError:
        raise RuntimeError(
            "PyMuPDF (fitz) não está instalado. "
            "Instale com: pip install PyMuPDF. "
            "Nota: instale com make install (requirements-dev.txt)."
        )

    pdf = fitz.open(stream=io.BytesIO(conteudo), filetype="pdf")
    num_paginas = len(pdf)

    textos_paginas = []
    paginas_com_texto = 0

    for pagina in pdf:
        texto = pagina.get_text()
        textos_paginas.append(texto)
        # Heurística: página com >100 chars = texto digital (não escaneado)
        if len(texto.strip()) > 100:
            paginas_com_texto += 1

    pdf.close()

    texto_completo = "\n\n".join(textos_paginas)
    qualidade = paginas_com_texto / num_paginas if num_paginas > 0 else 0.0

    return {
        "texto": texto_completo,
        "num_paginas": num_paginas,
        "qualidade_extracao": round(qualidade, 2),
        "metodo": "pymupdf",
    }
