"""
html2markdown.py — Extração de HTML como Markdown via html2text.

Segunda estratégia para documentos HTML (leis do planalto.gov.br).
Enquanto o `html_parser` (BeautifulSoup) retorna texto plano, este extrator
preserva a estrutura do documento em Markdown — títulos (`#`), listas, negrito —
tornando a comparação com `pymupdf4llm` válida e simétrica:

    html_parser    → texto plano   (equivalente a pymupdf)
    html2markdown  → Markdown      (equivalente a pymupdf4llm)

O html2text é leve, sem modelos ML, e preserva bem a hierarquia de artigos
e parágrafos das leis federais.
"""


def extrair_texto_html_markdown(html: str) -> dict:
    """
    Converte HTML em Markdown usando html2text.

    Args:
        html: string com o HTML completo da página

    Returns:
        dict com:
            texto (str): conteúdo em Markdown
            num_paginas (None): HTML não tem páginas
            qualidade_extracao (float): 1.0 se >1000 chars, 0.5 caso contrário
            formato_saida (str): sempre "markdown"
            extrator (str): sempre "html2markdown"
    """
    try:
        import html2text
    except ImportError:
        raise RuntimeError(
            "html2text não está instalado. Instale com: pip install html2text"
        )

    converter = html2text.HTML2Text()
    # Não quebrar URLs longas em múltiplas linhas
    converter.body_width = 0
    # Ignorar links — o texto regulatório não precisa deles
    converter.ignore_links = True
    # Ignorar imagens
    converter.ignore_images = True

    texto = converter.handle(html).strip()

    return {
        "texto": texto,
        "num_paginas": None,
        "qualidade_extracao": 1.0 if len(texto) > 1000 else 0.5,
        "formato_saida": "markdown",
        "extrator": "html2markdown",
    }
