"""
scraper_atos.py — Coleta de atos normativos da ANEEL (Power BI + cedoc/).

Por que este módulo existe?
---------------------------
Os atos normativos (RENs, REHs, Despachos, etc.) são a espinha dorsal do
corpus regulatório. O índice desses atos vive num relatório Power BI público
("Gestão do Estoque Regulatório"), e os PDFs ficam no diretório cedoc/.

Este módulo tem 2 responsabilidades:
1. **Consultar o Power BI** para obter a lista de atos com metadados
   (nome, situação, tipo, ementa, data)
2. **Baixar PDFs do cedoc/** para as RENs selecionadas

O diretório cedoc/ NÃO tem índice HTML (retorna 403) — por isso o Power BI
é o único ponto de descoberta estruturado.

Onde roda:
    Google Colab (Power BI API + download de PDFs + PyMuPDF)

Como usar:
    from src.ingestion.scraper_atos import consultar_powerbi, coletar_atos

    # 1. Obter o índice completo do Power BI
    atos = consultar_powerbi()
    vigentes = filtrar_vigentes(atos, tipo="ren")

    # 2. Baixar e extrair texto das RENs
    documentos = coletar_atos(vigentes)
"""

import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from src.config.settings import ANEEL_CEDOC_URL, ANEEL_POWERBI_URL, ANEEL_PROXY_URL
from src.ingestion.extractor import extrair_texto

# --- Constantes do Power BI ---
# Capturadas via Playwright inspecionando as requisições de rede (2026-05-28).
# Se a ANEEL atualizar o relatório, esses IDs podem mudar.
_POWERBI_RESOURCE_KEY = "3dcb7cfd-a90c-4d66-8ec3-6934cb4253de"
_POWERBI_DATASET_ID = "762a020c-217a-4dae-b9d3-d9b01fd2c14a"
_POWERBI_REPORT_ID = "cfda0c11-5d4e-4b61-ad42-7ef82d0be1f6"
_POWERBI_MODEL_ID = 5104124

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


# =========================================================================
# POWER BI — consulta e decodificação
# =========================================================================


def consultar_powerbi(
    propriedades: list[str] | None = None,
) -> list[dict]:
    """
    Consulta a API REST pública do Power BI da ANEEL.

    O Power BI expõe relatórios públicos via endpoint REST que aceita
    "semantic queries". O payload tem 3 partes:
    - From: tabelas do modelo (usamos "DIM Atos Normativos")
    - Select: colunas desejadas
    - Binding: agrupamento e limites

    A resposta usa formato DSR com dictionary encoding (compressão).
    Esta função já decodifica para uma lista de dicts Python.

    Args:
        propriedades: colunas a consultar. Default: todas as 5 descobertas.
            Válidas: "Resolução", "Situação", "Tipo", "Ementa", "Data"

    Returns:
        lista de dicts, um por ato normativo. Chaves = nomes das propriedades.
    """
    if propriedades is None:
        propriedades = ["Resolução", "Situação", "Tipo", "Ementa", "Data"]

    # Monta o Select no formato do Power BI
    select = []
    projections = []
    for i, prop in enumerate(propriedades):
        select.append(
            {
                "Column": {
                    "Expression": {"SourceRef": {"Source": "d"}},
                    "Property": prop,
                },
                "Name": f"DIM Atos Normativos.{prop}",
            }
        )
        projections.append(i)

    payload = {
        "version": "1.0.0",
        "queries": [
            {
                "Query": {
                    "Commands": [
                        {
                            "SemanticQueryDataShapeCommand": {
                                "Query": {
                                    "Version": 2,
                                    "From": [
                                        {
                                            "Name": "d",
                                            "Entity": "DIM Atos Normativos",
                                            "Type": 0,
                                        }
                                    ],
                                    "Select": select,
                                },
                                "Binding": {
                                    "Primary": {
                                        "Groupings": [{"Projections": projections}]
                                    },
                                    "DataReduction": {
                                        "DataVolume": 4,
                                        "Primary": {"Top": {"Count": 30000}},
                                    },
                                    "Version": 1,
                                },
                            }
                        }
                    ]
                },
                "QueryId": "",
                "ApplicationContext": {
                    "DatasetId": _POWERBI_DATASET_ID,
                    "Sources": [{"ReportId": _POWERBI_REPORT_ID}],
                },
            }
        ],
        "cancelQueries": [],
        "modelId": _POWERBI_MODEL_ID,
    }

    headers = {
        "X-PowerBI-ResourceKey": _POWERBI_RESOURCE_KEY,
        "Content-Type": "application/json;charset=UTF-8",
    }

    resp = requests.post(ANEEL_POWERBI_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    return _decodificar_dsr(resp.json(), propriedades)


def _decodificar_dsr(resposta_json: dict, propriedades: list[str]) -> list[dict]:
    """
    Decodifica a resposta DSR (Data Shape Result) do Power BI.

    O Power BI comprime respostas usando 2 técnicas:
    1. **ValueDicts** — valores repetidos viram índices num dicionário
    2. **R bitmask** — colunas que repetem da linha anterior são omitidas

    Args:
        resposta_json: JSON completo retornado pela API
        propriedades: nomes das colunas (mesma ordem do Select)

    Returns:
        lista de dicts decodificados
    """
    result = resposta_json["results"][0]["result"]["data"]
    ds = result["dsr"]["DS"][0]
    rows = ds["PH"][0]["DM0"]
    vdicts = ds.get("ValueDicts", {})

    # Schema da resposta — mapeia cada coluna ao seu ValueDict
    schema = rows[0].get("S", [])
    num_cols = len(schema)
    col_dicts = []
    for s in schema:
        dn = s.get("DN")
        col_dicts.append(vdicts.get(dn) if dn else None)

    # Decodifica linha por linha
    decoded = []
    prev = [None] * num_cols

    for row in rows:
        c = row.get("C", [])
        r_mask = row.get("R", 0)
        current = list(prev)

        c_idx = 0
        for col in range(num_cols):
            bit = 1 << col
            if not (r_mask & bit):
                if c_idx < len(c):
                    current[col] = c[c_idx]
                    c_idx += 1

        prev = list(current)

        # Resolve referências de dicionário
        record = {}
        for i, prop in enumerate(propriedades):
            val = current[i]
            d = col_dicts[i]
            if d is not None and isinstance(val, int):
                val = d[val]
            record[prop] = val

        decoded.append(record)

    return decoded


# =========================================================================
# Filtros e URLs
# =========================================================================


def filtrar_vigentes(atos: list[dict], sigla: str | None = None) -> list[dict]:
    """
    Filtra atos normativos vigentes (não revogados).

    No Power BI, a coluna "Situação" indica se o ato está vigente:
    - "Não consta revogação expressa" = vigente
    - "Vacatio Legis" = vigente (em período de vacância)

    Args:
        atos: lista de dicts retornada por consultar_powerbi()
        sigla: filtrar por tipo de ato (ex.: "ren", "res"). None = todos.

    Returns:
        lista filtrada
    """
    situacoes_vigentes = {"Não consta revogação expressa", "Vacatio Legis"}

    resultado = [a for a in atos if a.get("Situação") in situacoes_vigentes]

    if sigla:
        sigla_upper = sigla.upper()
        resultado = [
            a for a in resultado if a.get("Resolução", "").startswith(sigla_upper + " ")
        ]

    return resultado


def montar_url_ato(sigla: str, ano: int, numero: int) -> str:
    """
    Constrói a URL do PDF no cedoc/.

    Padrão: https://www2.aneel.gov.br/cedoc/{sigla_lower}{ano}{numero:04d}.pdf

    Args:
        sigla: tipo do ato (ex.: "ren", "res")
        ano: ano de publicação
        numero: número do ato
    """
    return f"{ANEEL_CEDOC_URL}/{sigla.lower()}{ano}{numero:04d}.pdf"


def montar_url_consolidada(sigla: str, ano: int, numero: int) -> str:
    """URL da versão consolidada (prefixo 'b')."""
    return f"{ANEEL_CEDOC_URL}/b{sigla.lower()}{ano}{numero:04d}.pdf"


def _parsear_resolucao(resolucao: str) -> tuple[str, int, int] | None:
    """
    Extrai sigla, número e ano do campo "Resolução" do Power BI.

    Formato: "REN 1000/2021", "RES 798/2002", "DSP 934/2008"

    Returns:
        tupla (sigla, numero, ano) ou None se não conseguir parsear
    """
    match = re.match(r"(\w+)\s+(\d+)/(\d{4})", resolucao)
    if not match:
        return None
    sigla, numero_str, ano_str = match.groups()
    return sigla, int(numero_str), int(ano_str)


# =========================================================================
# Download e coleta
# =========================================================================


def baixar_ato(sigla: str, ano: int, numero: int) -> bytes | None:
    """
    Baixa o PDF de um ato do cedoc/.

    Tenta primeiro a versão consolidada (mais completa, inclui alterações),
    depois a original. Retorna None para 404 (não crasha).

    Roteamento da requisição:
    - Se ANEEL_PROXY_URL estiver configurado → usa o Cloudflare Worker
      (necessário em Colab, GitHub Actions, e qualquer IP de data center)
    - Se vazio → tenta download direto (só funciona em IP residencial)

    Por que o Worker? O cedoc/ tem Cloudflare Bot Management que bloqueia
    IPs de data center com HTTP 403, independente de TLS fingerprint ou
    User-Agent. O Worker roda no edge da Cloudflare, que passa pelo bot
    management do próprio cedoc/. Ver DECISIONS.md.

    Args:
        sigla: tipo do ato (ex.: "ren")
        ano: ano de publicação
        numero: número do ato

    Returns:
        bytes do PDF, ou None se não encontrado
    """
    urls_cedoc = [
        (montar_url_consolidada(sigla, ano, numero), "consolidada"),
        (montar_url_ato(sigla, ano, numero), "original"),
    ]

    for url_cedoc, _label in urls_cedoc:
        # Se há proxy configurado, encapsula a URL no parâmetro ?url= do Worker
        if ANEEL_PROXY_URL:
            url_efetiva = f"{ANEEL_PROXY_URL.rstrip('/')}/?url={url_cedoc}"
        else:
            url_efetiva = url_cedoc

        try:
            resp = requests.get(url_efetiva, headers=_HEADERS, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except requests.RequestException:
            continue

    return None


def coletar_atos(atos: list[dict]) -> list[dict]:
    """
    Para cada ato da lista, baixa o PDF, extrai texto e monta dict do schema.

    Args:
        atos: lista de dicts do Power BI (precisa ter "Resolução", "Ementa",
              "Situação", "Data")

    Returns:
        lista de dicts no formato do schema do corpus
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos = []

    for ato in atos:
        resolucao = ato.get("Resolução", "")
        parsed = _parsear_resolucao(resolucao)
        if not parsed:
            print(f"  ⚠️  Formato inesperado: {resolucao}")
            continue

        sigla, numero, ano = parsed
        print(f"  Baixando {resolucao}...")

        pdf_bytes = baixar_ato(sigla, ano, numero)
        if pdf_bytes is None:
            print("    ❌ PDF não encontrado")
            continue

        try:
            resultado = extrair_texto(pdf_bytes, "pdf")
            print(
                f"    ✅ {resultado['num_paginas']} págs | "
                f"{len(resultado['texto'])} chars | "
                f"qualidade: {resultado['qualidade_extracao']}"
            )

            # Converter timestamp do Power BI (ms) para data
            data_pub = None
            data_raw = ato.get("Data")
            if data_raw and not pd.isna(data_raw):
                data_pub = pd.to_datetime(data_raw, unit="ms").strftime("%Y-%m-%d")

            # Montar ID: "ren-2021-1000"
            doc_id = f"{sigla.lower()}-{ano}-{numero}"

            # Verificar se versão consolidada foi usada
            url_original = montar_url_ato(sigla, ano, numero)
            url_consolidada = montar_url_consolidada(sigla, ano, numero)

            documentos.append(
                {
                    "id": doc_id,
                    "tipo": "ato_normativo",
                    "subtipo": sigla.lower(),
                    "numero": str(numero),
                    "ano": ano,
                    "titulo": ato.get("Ementa") or resolucao,
                    "assunto": None,
                    "situacao": "vigente",
                    "data_publicacao": data_pub,
                    "fonte": "cedoc",
                    "url_original": url_original,
                    "url_consolidado": url_consolidada,
                    "formato_original": "pdf",
                    "texto_bruto": resultado["texto"],
                    "num_paginas": resultado["num_paginas"],
                    "metodo_extracao": resultado["metodo"],
                    "qualidade_extracao": resultado["qualidade_extracao"],
                    "hf_path": None,
                    "scraped_at": scraped_at,
                }
            )

        except Exception as e:
            print(f"    ❌ Erro na extração: {e}")

        # Rate limiting — 2 segundos entre requests
        time.sleep(2)

    return documentos
