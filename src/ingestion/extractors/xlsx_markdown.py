"""
xlsx_markdown.py — Extração de XLSX como Markdown via pandas + tabulate.

Segunda estratégia para planilhas XLSX (manuais da ANEEL com tabelas
tarifárias, modelos de envio, etc.). Enquanto `openpyxl` (em office.py)
concatena célula por célula — perdendo a estrutura tabular —, este extrator
preserva cada aba como uma tabela Markdown:

    ## NomeDaAba

    | col1 | col2 |
    |------|------|
    | val  | val  |

Isso é fundamental para RAG: o LLM consegue ler a relação coluna↔valor.

Tudo em memória, sem ML.
"""

import io


def extrair_texto_xlsx_markdown(conteudo: bytes) -> dict:
    """
    Converte XLSX em Markdown — uma seção por aba, cada aba como tabela.

    Args:
        conteudo: bytes do arquivo XLSX

    Returns:
        dict com:
            texto (str): Markdown com seções `## NomeAba` e tabelas
            num_paginas (None): XLSX não tem paginação
            qualidade_extracao (float): 1.0 se >1000 chars, 0.5 caso contrário
            formato_saida (str): sempre "markdown"
            extrator (str): sempre "pandas_tabulate"
    """
    try:
        import pandas as pd

        # tabulate é dependência implícita do df.to_markdown() — importa para
        # garantir que está disponível e dar erro claro se faltar
        import tabulate  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "pandas e/ou tabulate não estão instalados. "
            "Instale com: pip install pandas tabulate"
        )

    excel = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
    partes: list[str] = []

    for nome_aba in excel.sheet_names:
        df = excel.parse(nome_aba)
        # Pular abas vazias — Excel costuma ter "Plan2" / "Plan3" em branco
        if df.empty:
            continue
        partes.append(f"## {nome_aba}\n")
        partes.append(df.to_markdown(index=False))
        partes.append("")  # linha em branco entre abas

    texto = "\n".join(partes).strip()

    return {
        "texto": texto,
        "num_paginas": None,
        "qualidade_extracao": 1.0 if len(texto) > 1000 else 0.5,
        "formato_saida": "markdown",
        "extrator": "pandas_tabulate",
    }
