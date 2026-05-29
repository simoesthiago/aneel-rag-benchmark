"""
parser.py — Limpeza e normalização de texto extraído.

Por que este módulo existe?
---------------------------
Texto extraído de PDFs e HTML vem com artefatos: espaços duplicados,
quebras de linha no meio de frases, números de página, headers repetidos.
Este módulo limpa esses artefatos para que o texto fique pronto para
chunking (Camada 2).

Para a Wave 1, a limpeza é mínima — normalização de whitespace e remoção
de artefatos óbvios. Chunking e parsing de estrutura (artigos, seções)
são responsabilidade da Camada 2.

Como usar:
    from src.ingestion.parser import limpar_texto

    texto_limpo = limpar_texto(texto_bruto)
"""

import re


def limpar_texto(texto: str) -> str:
    """
    Normaliza whitespace e remove artefatos comuns de extração.

    Limpezas aplicadas:
    1. Remove caracteres de controle (exceto \\n e \\t)
    2. Normaliza whitespace (múltiplos espaços → um)
    3. Remove linhas que são só números (páginas)
    4. Remove linhas muito curtas que parecem headers/footers repetidos

    Args:
        texto: texto bruto extraído por extractor.py

    Returns:
        texto limpo
    """
    if not texto:
        return ""

    # 1. Remover caracteres de controle (\\x00-\\x08, \\x0b, \\x0c, \\x0e-\\x1f)
    # Mantém \\n (\\x0a), \\t (\\x09) e \\r (\\x0d)
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)

    # 2. Normalizar whitespace horizontal (múltiplos espaços/tabs → um espaço)
    texto = re.sub(r"[^\S\n]+", " ", texto)

    # 3. Remover linhas que são apenas números (paginação)
    # Ex.: "42", "- 15 -", "Página 7"
    linhas = texto.split("\n")
    linhas_limpas = []
    for linha in linhas:
        stripped = linha.strip()
        # Pula linhas que são só número (com possível pontuação)
        if re.match(r"^[\s\-–—]*\d+[\s\-–—]*$", stripped):
            continue
        # Pula linhas tipo "Página X" ou "Page X"
        if re.match(r"^(página|page)\s+\d+$", stripped, re.IGNORECASE):
            continue
        linhas_limpas.append(linha)

    texto = "\n".join(linhas_limpas)

    # 4. Colapsar 3+ quebras de linha consecutivas em 2
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    # 5. Remover espaços em branco no início e fim
    texto = texto.strip()

    return texto
