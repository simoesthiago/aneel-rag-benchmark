"""
schema.py — Contrato do corpus: builder de documento, constantes e validação.

Por que este módulo existe?
---------------------------
Antes, cada scraper montava à mão o mesmo dict de 19 campos do schema. Quando o
schema mudava, era preciso editar 5+ arquivos. Aqui centralizamos:

1. `montar_documento(...)` — único lugar que conhece o formato de uma linha do
   corpus. Os scrapers passam os metadados da fonte + o `resultado` do extractor,
   e recebem o dict pronto.
2. `_SCHEMA_COLUNAS` / `_COLUNAS_NOT_NULL` — a definição das colunas.
3. `validar_schema(df)` — o gate de qualidade antes de subir ao Hub.

Schema completo e racional de design: ver docs/schema.md.

Unicidade (Opção A — múltiplas estratégias de extração):
    A chave de um documento no corpus é `(id, metodo_extracao)`, não só `id`.
    O mesmo documento (ex.: "ren-2021-1000") pode aparecer como `texto` e como
    `markdown` — duas linhas, mesmo `id`, `metodo_extracao` diferente.

Distinção entre `metodo_extracao` e `extrator`:
    - `metodo_extracao` ∈ {"texto", "markdown"} — formato de saída. Vira partição
      no Hub (`tipo=X/metodo_extracao=Y/`). É o eixo do benchmark.
    - `extrator` — ferramenta concreta ("pymupdf", "mammoth", "pandas_tabulate"…).
      Metadado de rastreio, viaja dentro do Parquet. Em manuais (formatos mistos)
      a mesma partição `markdown` pode ter linhas com extratores diferentes.
"""

import pandas as pd

from src.ingestion.extractors import FORMATOS_SAIDA_VALIDOS

# Colunas obrigatórias do schema (ver docs/schema.md)
_SCHEMA_COLUNAS = [
    "id",
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "assunto",
    "situacao",
    "data_publicacao",
    "fonte",
    "url_original",
    "url_consolidado",
    "formato_original",
    "texto_bruto",
    "num_paginas",
    "metodo_extracao",
    "extrator",
    "qualidade_extracao",
    "hf_path",
    "scraped_at",
]

# Colunas que NUNCA devem ser nulas
_COLUNAS_NOT_NULL = [
    "id",
    "tipo",
    "titulo",
    "fonte",
    "url_original",
    "formato_original",
    "texto_bruto",
    "metodo_extracao",
    "extrator",
    "scraped_at",
]

# Chave de unicidade de uma linha do corpus (Opção A: doc × estratégia).
_CHAVE_UNICA = ["id", "metodo_extracao"]


def montar_documento(
    *,
    id: str,
    tipo: str,
    subtipo: str | None,
    numero: str | None,
    ano: int | None,
    titulo: str,
    assunto: str | None,
    situacao: str | None,
    data_publicacao: str | None,
    fonte: str,
    url_original: str,
    url_consolidado: str | None,
    formato_original: str,
    resultado: dict,
    scraped_at: str,
) -> dict:
    """
    Monta uma linha do corpus a partir dos metadados da fonte + resultado do extractor.

    Os 5 campos derivados da extração (`texto_bruto`, `num_paginas`,
    `metodo_extracao`, `extrator`, `qualidade_extracao`) são preenchidos a partir
    de `resultado` — o dict retornado por `extractors.extrair_texto`. Assim os
    scrapers não precisam saber qual ferramenta rodou: tudo vem no resultado.

    Args:
        resultado: dict do extractor com texto/num_paginas/qualidade_extracao/
            formato_saida/extrator
        (demais args): metadados específicos da fonte

    Returns:
        dict com as 20 colunas do schema, pronto para virar linha do DataFrame
    """
    return {
        "id": id,
        "tipo": tipo,
        "subtipo": subtipo,
        "numero": numero,
        "ano": ano,
        "titulo": titulo,
        "assunto": assunto,
        "situacao": situacao,
        "data_publicacao": data_publicacao,
        "fonte": fonte,
        "url_original": url_original,
        "url_consolidado": url_consolidado,
        "formato_original": formato_original,
        "texto_bruto": resultado["texto"],
        "num_paginas": resultado["num_paginas"],
        "metodo_extracao": resultado["formato_saida"],
        "extrator": resultado["extrator"],
        "qualidade_extracao": resultado["qualidade_extracao"],
        "hf_path": None,
        "scraped_at": scraped_at,
    }


def validar_schema(df: pd.DataFrame) -> None:
    """
    Valida que o DataFrame segue o schema do corpus.

    Verifica:
    1. Todas as colunas obrigatórias estão presentes
    2. Nenhuma coluna NOT NULL contém nulos
    3. Não há pares (id, metodo_extracao) duplicados
    4. texto_bruto não está vazio em nenhum documento
    5. metodo_extracao ∈ {"texto", "markdown"} (só esses dois valores no Hub)

    Args:
        df: DataFrame com os documentos

    Raises:
        RuntimeError: se alguma validação falhar (mensagem explica o problema)
    """
    # 1. Colunas presentes
    colunas_faltando = set(_SCHEMA_COLUNAS) - set(df.columns)
    if colunas_faltando:
        raise RuntimeError(
            f"Colunas faltando no DataFrame: {colunas_faltando}. "
            f"O schema exige: {_SCHEMA_COLUNAS}"
        )

    # 2. Colunas NOT NULL
    for col in _COLUNAS_NOT_NULL:
        nulos = df[df[col].isna()]
        if len(nulos) > 0:
            ids_nulos = nulos["id"].tolist()[:5]
            raise RuntimeError(
                f"Coluna obrigatória '{col}' tem {len(nulos)} valores nulos. "
                f"IDs afetados (primeiros 5): {ids_nulos}"
            )

    # 3. Pares (id, metodo_extracao) únicos — Opção A: doc pode repetir entre estratégias
    duplicados = df[df.duplicated(subset=_CHAVE_UNICA, keep=False)]
    if len(duplicados) > 0:
        pares_dup = (
            duplicados[_CHAVE_UNICA].drop_duplicates().to_dict("records")
        )
        raise RuntimeError(
            f"Pares (id, metodo_extracao) duplicados: {pares_dup}. "
            f"Cada documento precisa ser único por estratégia de extração."
        )

    # 4. texto_bruto não vazio
    vazios = df[df["texto_bruto"].str.len() < 100]
    if len(vazios) > 0:
        ids_vazios = vazios["id"].tolist()
        raise RuntimeError(
            f"{len(vazios)} documentos com texto_bruto < 100 chars: {ids_vazios}. "
            f"Extração de texto provavelmente falhou."
        )

    # 5. metodo_extracao ∈ {"texto", "markdown"}
    # Falha cedo se algum extrator esquecer de declarar formato_saida ou se um
    # nome de ferramenta antigo vazar para a coluna (ex.: "pymupdf", "docling").
    metodos_invalidos = set(df["metodo_extracao"].unique()) - FORMATOS_SAIDA_VALIDOS
    if metodos_invalidos:
        raise RuntimeError(
            f"metodo_extracao com valores inválidos: {metodos_invalidos}. "
            f"Aceitos: {sorted(FORMATOS_SAIDA_VALIDOS)}. "
            f"Provavelmente um extrator está retornando o nome da ferramenta "
            f"em vez do formato de saída."
        )
