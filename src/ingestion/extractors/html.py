"""
html.py — Extração de texto de páginas HTML via BeautifulSoup.

Usado pelas leis do planalto.gov.br (HTML estático). Estratégia única para o
formato — não há benchmark de extração de HTML (BeautifulSoup cobre bem o caso).
"""

from bs4 import BeautifulSoup


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
