"""
mammoth_md.py — Extração de DOCX como Markdown via mammoth + html2text.

Segunda estratégia para documentos DOCX (manuais da ANEEL). Enquanto
`python_docx` (em office.py) só recupera os parágrafos como texto plano,
este extrator preserva a estrutura semântica do documento:

    DOCX → HTML (mammoth)
         → Markdown (html2text)

Por que dois passos?
--------------------
O `mammoth` é a biblioteca canônica para extrair DOCX preservando títulos
(Heading 1/2/3), listas e tabelas. Ele exporta HTML semântico — depois
converter HTML→Markdown é trivial (mesma engine já usada em `html2markdown.py`).

Tudo em memória, sem ML, sem dependência de torch.
"""

import io


def extrair_texto_docx_markdown(conteudo: bytes) -> dict:
    """
    Converte DOCX em Markdown via mammoth → html2text.

    Args:
        conteudo: bytes do arquivo DOCX

    Returns:
        dict com:
            texto (str): conteúdo em Markdown
            num_paginas (None): DOCX não expõe paginação confiável
            qualidade_extracao (float): 1.0 se >1000 chars, 0.5 caso contrário
            formato_saida (str): sempre "markdown"
            extrator (str): sempre "mammoth"
    """
    try:
        import mammoth
        import html2text
    except ImportError:
        raise RuntimeError(
            "mammoth e/ou html2text não estão instalados. "
            "Instale com: pip install mammoth html2text"
        )

    # mammoth retorna um objeto com .value (HTML) e .messages (avisos do parser)
    resultado_html = mammoth.convert_to_html(io.BytesIO(conteudo))
    html = resultado_html.value

    # Reusa a mesma config do html2markdown.py — comportamento consistente entre
    # as duas estratégias HTML→Markdown do projeto
    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_links = True
    converter.ignore_images = True

    texto = converter.handle(html).strip()

    return {
        "texto": texto,
        "num_paginas": None,
        "qualidade_extracao": 1.0 if len(texto) > 1000 else 0.5,
        "formato_saida": "markdown",
        "extrator": "mammoth",
    }
