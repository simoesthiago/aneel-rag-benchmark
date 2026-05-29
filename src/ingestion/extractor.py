"""
extractor.py — Extração de texto de documentos em diversos formatos.

Por que este módulo existe?
---------------------------
O corpus da ANEEL vem em formatos variados: PDFs (atos normativos), HTML
(leis do planalto.gov.br), DOCX e XLSX (manuais). Cada formato exige um
parser diferente, mas todos os scrapers precisam da mesma coisa no final:
texto limpo + metadados de qualidade.

Este módulo centraliza essa lógica para que os scrapers não precisem saber
os detalhes de cada parser — eles só chamam `extrair_texto(conteudo, formato)`.

Onde roda:
    - PDF: Google Colab (PyMuPDF exige compilação nativa)
    - HTML: qualquer lugar (BeautifulSoup é Python puro)
    - DOCX/XLSX: Wave 3 — levanta NotImplementedError por enquanto

Como usar:
    from src.ingestion.extractor import extrair_texto

    resultado = extrair_texto(pdf_bytes, "pdf")
    # resultado = {"texto": "...", "num_paginas": 42, "qualidade_extracao": 0.95, ...}
"""

import io
from bs4 import BeautifulSoup


def extrair_texto_pdf(conteudo: bytes) -> dict:
    """
    Extrai texto de um PDF usando PyMuPDF (fitz).

    Processa o PDF inteiramente em memória — NUNCA salva em disco.
    Isso é fundamental: o projeto opera com a premissa de que dados brutos
    não tocam a máquina local (Colab → HF Hub direto).

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
            "Nota: este módulo roda melhor no Google Colab."
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


def extrair_texto_html(html: str) -> dict:
    """
    Extrai texto limpo de uma página HTML.

    Remove scripts, estilos e navegação. Mantém apenas parágrafos com
    conteúdo substancial (>10 chars) para eliminar resíduos de layout.

    Args:
        html: string com o HTML completo da página

    Returns:
        dict com:
            texto (str): texto limpo extraído
            num_paginas (None): HTML não tem páginas
            qualidade_extracao (float): 1.0 se >1000 chars, 0.5 caso contrário
            metodo (str): sempre "html_parser"
    """
    soup = BeautifulSoup(html, "lxml")

    # Remover tags que não contêm conteúdo útil
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # Extrair parágrafos com conteúdo substancial
    paragrafos = soup.find_all("p")
    texto_partes = []
    for p in paragrafos:
        texto = p.get_text(strip=True)
        if texto and len(texto) > 10:
            texto_partes.append(texto)

    texto_final = "\n\n".join(texto_partes)

    return {
        "texto": texto_final,
        "num_paginas": None,
        "qualidade_extracao": 1.0 if len(texto_final) > 1000 else 0.5,
        "metodo": "html_parser",
    }


def extrair_texto(conteudo: bytes | str, formato: str) -> dict:
    """
    Dispatcher principal — extrai texto de qualquer formato suportado.

    Este é o ponto de entrada que os scrapers usam. Delega para o extrator
    específico de cada formato.

    Args:
        conteudo: bytes (PDF, DOCX, XLSX) ou str (HTML)
        formato: "pdf", "html", "docx", "xlsx"

    Returns:
        dict com texto, num_paginas, qualidade_extracao, metodo

    Raises:
        NotImplementedError: para formatos ainda não implementados (DOCX, XLSX)
        ValueError: para formatos desconhecidos
    """
    formato_lower = formato.lower()

    if formato_lower == "pdf":
        if not isinstance(conteudo, bytes):
            raise TypeError("Para PDF, conteudo deve ser bytes.")
        return extrair_texto_pdf(conteudo)

    elif formato_lower == "html":
        if isinstance(conteudo, bytes):
            # Tenta decodificar como UTF-8, com fallback para latin-1
            try:
                conteudo = conteudo.decode("utf-8")
            except UnicodeDecodeError:
                conteudo = conteudo.decode("latin-1")
        return extrair_texto_html(conteudo)

    elif formato_lower == "docx":
        raise NotImplementedError(
            "Extração de DOCX será implementada na Wave 3. " "Biblioteca: python-docx."
        )

    elif formato_lower == "xlsx":
        raise NotImplementedError(
            "Extração de XLSX será implementada na Wave 3. " "Biblioteca: openpyxl."
        )

    else:
        raise ValueError(
            f"Formato '{formato}' não é suportado. "
            f"Formatos válidos: pdf, html, docx, xlsx."
        )
