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
    Máquina local com IP residencial brasileiro (cedoc/ bloqueia datacenters)

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
import urllib.parse
from datetime import datetime, timezone

import pandas as pd
import requests

from curl_cffi import requests as cffi_requests

from src.config.settings import ANEEL_CEDOC_URL, ANEEL_POWERBI_URL
from src.ingestion.extractor import extrair_texto

# --- Constantes do Power BI ---
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


_SITUACOES_VIGENTES = frozenset(
    {"Não consta revogação expressa", "Vacatio Legis"}
)


def _mapear_situacao(situacao_powerbi: str | None) -> str:
    """Converte situação do Power BI para o schema (`vigente` / `revogada`)."""
    if situacao_powerbi in _SITUACOES_VIGENTES:
        return "vigente"
    return "revogada"


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
    resultado = [a for a in atos if a.get("Situação") in _SITUACOES_VIGENTES]

    if sigla:
        sigla_upper = sigla.upper()
        resultado = [
            a for a in resultado if a.get("Resolução", "").startswith(sigla_upper + " ")
        ]

    return resultado


def filtrar_nao_vigentes(atos: list[dict], sigla: str | None = None) -> list[dict]:
    """
    Filtra atos normativos não vigentes (revogados ou outras situações).

    Complemento de `filtrar_vigentes` — usado na Wave 3 para ingestão incremental.
    """
    resultado = [a for a in atos if a.get("Situação") not in _SITUACOES_VIGENTES]

    if sigla:
        sigla_upper = sigla.upper()
        resultado = [
            a
            for a in resultado
            if a.get("Resolução", "").startswith(sigla_upper + " ")
        ]

    return resultado


def montar_url_ato(sigla: str, ano: int, numero: int) -> str:
    """
    Constrói a URL do PDF no cedoc/.

    Padrão: https://www2.aneel.gov.br/cedoc/{sigla_lower}{ano}{numero}.pdf

    Importante: o cedoc/ NÃO usa zero-padding no número.
    Ex.: REN 920/2021 → ren2021920.pdf (não ren20210920.pdf).
    Isso só foi descoberto ao testar com RENs de número < 1000 —
    o teste anterior usava REN 1000 que tem 4 dígitos de qualquer forma.

    Args:
        sigla: tipo do ato (ex.: "ren", "res")
        ano: ano de publicação
        numero: número do ato
    """
    return f"{ANEEL_CEDOC_URL}/{sigla.lower()}{ano}{numero}.pdf"


def montar_url_consolidada(sigla: str, ano: int, numero: int) -> str:
    """URL da versão consolidada (prefixo 'b'). Também sem zero-padding."""
    return f"{ANEEL_CEDOC_URL}/b{sigla.lower()}{ano}{numero}.pdf"


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


def _resposta_e_pdf_valido(status: int, content: bytes) -> bool:
    """True se HTTP 200 e corpo parece PDF (não página HTML de erro/bloqueio)."""
    return status == 200 and len(content) > 1000 and content[:4] == b"%PDF"


def _diagnostico_http(label: str, status: int, content: bytes) -> None:
    """Log curto quando o download falha — ajuda a distinguir 403 vs 404."""
    inicio = content[:60].decode("utf-8", errors="replace").replace("\n", " ")
    print(f"    [{label}] HTTP {status} | {len(content)} bytes | início: {inicio[:70]!r}")


def _baixar_url_cedoc(url: str, label: str) -> bytes | None:
    """
    Baixa uma URL do cedoc/ via curl_cffi com TLS impersonation.

    O cedoc/ usa Cloudflare Bot Management com TLS fingerprinting — requests
    normal retorna 403. curl_cffi com impersonate="chrome120" mimetiza o
    handshake TLS do Chrome real e é aceito.

    Requer IP residencial brasileiro: o cedoc/ bloqueia qualquer IP de
    datacenter (cloud providers, CDNs). Roda na máquina local do desenvolvedor.
    """
    try:
        resp = cffi_requests.get(url, impersonate="chrome120", timeout=60)
        if _resposta_e_pdf_valido(resp.status_code, resp.content):
            return resp.content
        # 4xx = arquivo não existe — diagnóstico e para
        if 400 <= resp.status_code < 500:
            _diagnostico_http(label, resp.status_code, resp.content)
            return None
        # 5xx — problema temporário no servidor
        _diagnostico_http(label, resp.status_code, resp.content)
    except Exception as e:
        print(f"    [{label}] erro de rede: {e}")

    return None


def baixar_ato(sigla: str, ano: int, numero: int) -> bytes | None:
    """
    Baixa o PDF de um ato do cedoc/.

    Tenta primeiro a versão consolidada (mais completa, inclui alterações),
    depois a original. Retorna None se nenhuma versão for encontrada.

    O cedoc/ usa Cloudflare Bot Management com TLS fingerprinting.
    curl_cffi com impersonate="chrome120" mimetiza o handshake TLS do Chrome
    real — único método que funciona de IP residencial brasileiro.

    Args:
        sigla: tipo do ato (ex.: "ren")
        ano: ano de publicação
        numero: número do ato

    Returns:
        bytes do PDF, ou None se não encontrado
    """
    # Original primeiro: consolidada costuma 404 em muitas RENs.
    urls = [
        (montar_url_ato(sigla, ano, numero), "original"),
        (montar_url_consolidada(sigla, ano, numero), "consolidada"),
    ]

    for url, label in urls:
        pdf = _baixar_url_cedoc(url, label)
        if pdf is not None:
            return pdf

    return None


def coletar_atos(atos: list[dict], max_atos: int | None = None) -> list[dict]:
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
    lista = atos[:max_atos] if max_atos is not None else atos

    for ato in lista:
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
                    "situacao": _mapear_situacao(ato.get("Situação")),
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
