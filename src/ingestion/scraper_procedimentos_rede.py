"""
scraper_procedimentos_rede.py — Coleta dos Procedimentos de Rede do ONS.

Por que este módulo existe?
---------------------------
Os Procedimentos de Rede são as regras que todas as distribuidoras, geradoras
e transmissoras reguladas pela ANEEL devem seguir para operar no SIN (Sistema
Interligado Nacional). Embora sejam propostos pelo ONS, parte deles é aprovada
pela própria ANEEL (REN 903/2020). O portal da ANEEL os lista explicitamente
como Procedimentos Regulatórios — fazem parte do repositório regulatório.

Os documentos ficam num SharePoint público do ONS, acessível sem autenticação.
O SharePoint expõe uma API REST que retorna metadados estruturados com flag
`vigente`, o que dispensa navegação HTML e é mais confiável que scraping de
accordions renderizados por JS.

Fonte: SharePoint ONS via proxy público
    API:      proxyportais.ons.org.br/ons.portalempregado.proxy/garproxy/_api/
    Download: proxyportais.ons.org.br/ons.portalempregado.proxy/garapi/api/processo/retornarpdf

Estrutura:
    - 9 módulos, ~50 submódulos, ~165 documentos vigentes
    - Cada documento é um DOCX no SharePoint; o proxy o serve como PDF
    - Tipos de documento: Operacional (ONS), Requisitos, Procedimental,
      Responsabilidades, Definição, Metodologia, Critérios, Indicadores (ANEEL)

Como usar:
    from src.ingestion.scraper_procedimentos_rede import coletar_procedimentos_rede

    documentos = coletar_procedimentos_rede()
"""

import re
import time
import urllib.parse
from datetime import datetime, timezone

import requests

from src.config.settings import ONS_PROXY_URL
from src.ingestion.extractor import extrair_texto

# Endpoint da API REST SharePoint que lista os documentos de Procedimentos de Rede.
# ContentTypeId filtra só documentos de procedimento (exclui outros itens da lista).
_API_URL = (
    f"{ONS_PROXY_URL}/garproxy/_api/web/lists/getbytitle('ecm-documents')/items"
    "?$select=Id,Title,modulo,subModulo,tipoDocumento,revisao,"
    "vigenciaInicio,vigenciaFim,vigente,File/Name,File/ServerRelativeUrl"
    "&$expand=File"
    "&$filter=(ContentTypeId%20eq%20'0x01007804C612865B0049A34ECAAA0B89AE94')"
    "%20and%20(vigente%20eq%20'Vigente')"
    "&$top=5000"
)

_PDF_PROXY = f"{ONS_PROXY_URL}/garapi/api/processo/retornarpdf"

_REQUEST_TIMEOUT_S = 90
_SLEEP_BETWEEN_S = 0.5


def _pdf_url(server_relative_url: str) -> str:
    """
    Constrói a URL do proxy que serve o PDF a partir do caminho SharePoint do DOCX.

    O SharePoint armazena os arquivos em /ecmdocuments/ como .docx.
    O proxy serve versões PDF convertidas de /ecmpdf/ com extensão .pdf.
    """
    pdf_path = (
        server_relative_url
        .replace("/ecmdocuments/", "/ecmpdf/")
        .replace(".docx", ".pdf")
    )
    return f"{_PDF_PROXY}?url={urllib.parse.quote(pdf_path, safe='/:')}"


def _id_de_arquivo(nome_arquivo: str) -> str:
    """
    Gera id estável a partir do nome do arquivo DOCX.

    Exemplos:
        'Submódulo 1.1-OP_2020.12.docx' → 'proc-rede-1-1-op'
        'Submódulo 2.10-RQ_2025.02.docx' → 'proc-rede-2-10-rq'
    """
    m = re.match(r"[Ss]ub[mM][oó]dulo\s+([\d.]+)-([A-Z]+)_", nome_arquivo)
    if m:
        num = m.group(1).replace(".", "-")
        tipo = m.group(2).lower()
        return f"proc-rede-{num}-{tipo}"
    # Fallback para nomes fora do padrão
    slug = re.sub(r"[^a-z0-9]+", "-", nome_arquivo.lower().replace(".docx", ""))
    return f"proc-rede-{slug[:40]}"


def listar_vigentes() -> list[dict]:
    """
    Consulta a API SharePoint do ONS e retorna metadados dos submódulos vigentes.

    O SharePoint do ONS permite acesso anônimo (usuário 1073741822 = Everyone).
    Não é necessário nenhum token de autenticação.

    Returns:
        lista de dicts com campos do SharePoint (modulo, subModulo, tipoDocumento, etc.)
    """
    resp = requests.get(
        _API_URL,
        headers={"Accept": "application/json"},
        timeout=_REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


def coletar_procedimentos_rede() -> list[dict]:
    """
    Coleta os ~165 Procedimentos de Rede vigentes do ONS e extrai texto dos PDFs.

    Processo:
        1. Consulta API SharePoint filtrando vigente='Vigente'
        2. Para cada item, constrói URL do PDF via proxy de conversão DOCX→PDF
        3. Baixa o PDF e extrai texto com PyMuPDF

    Returns:
        lista de dicts no formato do schema do corpus (docs/schema.md)
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos: list[dict] = []

    print("Coletando Procedimentos de Rede (ONS SharePoint API)...")

    try:
        vigentes = listar_vigentes()
    except Exception as e:
        print(f"  ❌ Erro ao consultar API ONS: {e}")
        return []

    print(f"  {len(vigentes)} submódulos vigentes encontrados")

    for item in vigentes:
        submodulo = item.get("subModulo", "")
        tipo_doc = item.get("tipoDocumento", "")
        modulo = item.get("modulo", "")
        revisao = item.get("revisao", "")
        titulo_item = item.get("Title", submodulo)
        file_info = item.get("File", {})
        nome_arquivo = file_info.get("Name", "")
        server_url = file_info.get("ServerRelativeUrl", "")

        if not server_url or not nome_arquivo:
            print(f"  ⚠️  Sem arquivo: {submodulo}")
            continue

        doc_id = _id_de_arquivo(nome_arquivo)
        pdf_url = _pdf_url(server_url)

        # Número do submódulo: "1.1 - Descrição" → "1.1"
        num_submod = submodulo.split(" - ")[0].strip() if " - " in submodulo else submodulo

        # Código do tipo (ex.: OP, RS) a partir do nome do arquivo
        tipo_match = re.search(r"-([A-Z]+)_", nome_arquivo)
        tipo_code = tipo_match.group(1) if tipo_match else ""
        numero = f"{num_submod}-{tipo_code}" if tipo_code else num_submod

        print(f"  {doc_id}: {submodulo[:60]}")

        try:
            resp = requests.get(pdf_url, timeout=_REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            pdf_bytes = resp.content

            resultado = extrair_texto(pdf_bytes, "pdf")

            if len(resultado["texto"].strip()) < 100:
                print(f"    ⚠️  Texto muito curto — pulando")
                continue

            # Ano de vigência ou revisão
            ano: int | None = None
            vigencia_inicio = item.get("vigenciaInicio") or ""
            if vigencia_inicio:
                ano = int(vigencia_inicio[:4])
            elif revisao:
                try:
                    ano = int(revisao.split(".")[0])
                except ValueError:
                    pass

            data_pub = vigencia_inicio[:10] if vigencia_inicio else None

            print(
                f"    ✅ {resultado['num_paginas']} págs | "
                f"{len(resultado['texto'])} chars | "
                f"qualidade: {resultado['qualidade_extracao']}"
            )

            documentos.append(
                {
                    "id": doc_id,
                    "tipo": "procedimento",
                    "subtipo": "procedimento_rede",
                    "numero": numero,
                    "ano": ano,
                    "titulo": f"Procedimentos de Rede — {titulo_item}",
                    "assunto": modulo,
                    "situacao": None,
                    "data_publicacao": data_pub,
                    "fonte": "ons_org_br",
                    "url_original": pdf_url,
                    "url_consolidado": None,
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
            print(f"    ❌ Erro ao baixar/extrair {nome_arquivo}: {e}")

        time.sleep(_SLEEP_BETWEEN_S)

    print(f"\n✅ {len(documentos)} Procedimentos de Rede coletados.")
    return documentos
