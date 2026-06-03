"""
scraper_procedimentos.py — Coleta de procedimentos regulatórios via GitLab.

Por que este módulo existe?
---------------------------
Os procedimentos regulatórios da ANEEL ficam num GitLab público
(git.aneel.gov.br/publico/centralconteudo). Este módulo usa a API REST
do GitLab para descobrir e baixar PDFs.

O GitLab não exige autenticação para projetos públicos.

Subcategorias de Procedimentos Regulatórios (5 no portal gov.br):
    1. PRODIST (11 módulos) — Procedimentos de Distribuição → GitLab: procreg/prodist/
    2. PRORET — Procedimentos de Regulação Tarifária → GitLab: procreg/proret/
    3. Regras de Transmissão (6 módulos) → GitLab: procreg/regtransm/
    4. Procedimentos de Rede → scraper_procedimentos_rede.py (ONS SharePoint)
    5. EE/P&D (PROPEE + PROPDI) → FORA DO ESCOPO (são RENs, já cobertas por scraper_atos.py)

Este scraper cobre as subcategorias 1, 2 e 3 — todas no mesmo GitLab.

Onde roda:
    Máquina local (API REST + download de PDFs + PyMuPDF)

Como usar:
    from src.ingestion.scraper_procedimentos import (
        listar_arquivos_gitlab,
        coletar_prodist_modulo,
        coletar_proret,
        coletar_regras_transmissao,
    )

    documentos = coletar_prodist_modulo(1)
    documentos += coletar_regras_transmissao()
"""

import re
import time
import urllib.parse
import warnings
from datetime import datetime, timezone

import requests
import urllib3

# git.aneel.gov.br usa certificado intermediário não reconhecido pelo Python/macOS.
# Suprimimos o aviso para não poluir o output do pipeline.
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

from src.config.settings import ANEEL_GITLAB_URL, ANEEL_GITLAB_PROJECT
from src.ingestion.extractors import extrair_texto
from src.ingestion.schema import montar_documento

# Path do projeto URL-encoded (GitLab aceita path ou ID numérico)
_GITLAB_PROJECT_PATH = urllib.parse.quote(ANEEL_GITLAB_PROJECT, safe="")

# Retry em timeout — o GitLab da ANEEL pode demorar em horários de pico
_GITLAB_MAX_RETRIES = 3
_GITLAB_RETRY_BACKOFF_S = 10
_GITLAB_TIMEOUT_S = 120


def _gitlab_get(url: str, params: dict | None = None) -> requests.Response:
    """
    GET com retry em timeout/conexão para a API do GitLab da ANEEL.

    O git.aneel.gov.br pode ser lento em horários de pico — 3 tentativas
    com backoff de 10/20s cobrem instabilidades transitórias.
    """
    last_error: Exception | None = None
    for attempt in range(_GITLAB_MAX_RETRIES):
        try:
            # verify=False: git.aneel.gov.br usa certificado intermediário que o
            # Python no macOS não consegue verificar via bundled certs. O risco é
            # aceitável — é um servidor gov.br acessado por HTTPS.
            resp = requests.get(
                url, params=params, timeout=_GITLAB_TIMEOUT_S, verify=False
            )
            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < _GITLAB_MAX_RETRIES - 1:
                wait = _GITLAB_RETRY_BACKOFF_S * (attempt + 1)
                print(
                    f"    GitLab: tentativa {attempt + 1}/{_GITLAB_MAX_RETRIES} "
                    f"falhou ({e!r}), retry em {wait}s..."
                )
                time.sleep(wait)
    raise last_error  # type: ignore[misc]


def listar_arquivos_gitlab(path: str = "") -> list[dict]:
    """
    Lista arquivos e pastas num caminho do repositório GitLab.

    Usa a API REST v4 do GitLab: /api/v4/projects/{id}/repository/tree

    Args:
        path: caminho dentro do repositório (ex.: "PRODIST", "PRODIST/Módulo 1")

    Returns:
        lista de dicts com: name, path, type ("tree" ou "blob")
    """
    url = (
        f"{ANEEL_GITLAB_URL}/api/v4/projects/" f"{_GITLAB_PROJECT_PATH}/repository/tree"
    )
    params = {"path": path, "per_page": 100}

    resp = _gitlab_get(url, params=params)
    return resp.json()


def baixar_arquivo_gitlab(file_path: str, ref: str = "main") -> bytes:
    """
    Baixa o conteúdo raw de um arquivo do repositório GitLab.

    Args:
        file_path: caminho completo do arquivo no repo
        ref: branch (default "master", pode ser "main")

    Returns:
        bytes do arquivo
    """
    file_path_encoded = urllib.parse.quote(file_path, safe="")
    url = (
        f"{ANEEL_GITLAB_URL}/api/v4/projects/"
        f"{_GITLAB_PROJECT_PATH}/repository/files/"
        f"{file_path_encoded}/raw"
    )
    params = {"ref": ref}

    resp = _gitlab_get(url, params=params)
    return resp.content


def _encontrar_pdf_em_pasta(path: str) -> str | None:
    """
    Procura o primeiro arquivo PDF dentro de uma pasta do GitLab.

    Returns:
        path completo do PDF, ou None se não encontrado
    """
    try:
        itens = listar_arquivos_gitlab(path)
        for item in itens:
            if item["name"].lower().endswith(".pdf") and item["type"] == "blob":
                return item["path"]
    except Exception:
        pass
    return None


def coletar_prodist_modulo(modulo: int, estrategia: str = "texto") -> list[dict]:
    """
    Coleta PDFs de um módulo específico do PRODIST.

    Navega pela estrutura do GitLab para encontrar o módulo desejado,
    baixa o(s) PDF(s) e extrai texto.

    Args:
        modulo: número do módulo (1 a 11)

    Returns:
        lista de dicts no formato do schema do corpus
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos = []

    # Encontrar a pasta PRODIST na raiz do repositório
    print("  Procurando PRODIST no GitLab...")
    try:
        itens_raiz = listar_arquivos_gitlab("")
    except Exception as e:
        print(f"    ❌ Erro ao acessar GitLab: {e}")
        return []

    prodist_path = None
    for item in itens_raiz:
        if "prodist" in item["name"].lower() and item["type"] == "tree":
            prodist_path = item["path"]
            break

    # Se não achou na raiz, procura um nível mais fundo
    if prodist_path is None:
        for item in itens_raiz:
            if item["type"] == "tree":
                try:
                    sub_itens = listar_arquivos_gitlab(item["path"])
                    for sub in sub_itens:
                        if "prodist" in sub["name"].lower() and sub["type"] == "tree":
                            prodist_path = sub["path"]
                            break
                except Exception:
                    pass
            if prodist_path:
                break

    if prodist_path is None:
        print("    ❌ Pasta PRODIST não encontrada no GitLab.")
        return []

    print(f"    ✅ PRODIST encontrado em: {prodist_path}")

    # Listar módulos dentro do PRODIST
    prodist_itens = listar_arquivos_gitlab(prodist_path)

    # Procurar o módulo específico
    modulo_str = str(modulo)
    modulo_str_padded = f"{modulo:02d}"  # "01", "02", ..., "11"
    modulo_path = None
    for item in prodist_itens:
        nome_lower = item["name"].lower()
        # Procura variações: "Módulo 1", "Modulo 1", "módulo1", "modulo01", etc.
        if (
            f"módulo {modulo_str}" in nome_lower
            or f"modulo {modulo_str}" in nome_lower
            or f"módulo{modulo_str}" in nome_lower
            or f"modulo{modulo_str}" in nome_lower
            or f"modulo{modulo_str_padded}" in nome_lower  # ex: "modulo01"
            or f"módulo{modulo_str_padded}" in nome_lower  # ex: "módulo01"
        ):
            if item["type"] == "tree":
                modulo_path = item["path"]
            elif item["name"].lower().endswith(".pdf"):
                modulo_path = item["path"]
            break

    if modulo_path is None:
        print(f"    ❌ Módulo {modulo} não encontrado dentro de {prodist_path}")
        print(f"    Itens disponíveis: {[i['name'] for i in prodist_itens]}")
        return []

    # Se é uma pasta, procurar o PDF dentro
    pdf_path = modulo_path
    if not modulo_path.lower().endswith(".pdf"):
        pdf_path = _encontrar_pdf_em_pasta(modulo_path)
        if pdf_path is None:
            print(f"    ❌ Nenhum PDF encontrado em {modulo_path}")
            return []

    print(f"    Baixando: {pdf_path}")

    # Baixar e extrair texto
    try:
        pdf_bytes = baixar_arquivo_gitlab(pdf_path, ref="main")
        print(f"    ✅ {len(pdf_bytes) / 1024:.0f} KB baixados")

        resultado = extrair_texto(pdf_bytes, "pdf", formato_saida=estrategia)
        print(
            f"    📄 {resultado['num_paginas']} págs | "
            f"{len(resultado['texto'])} chars | "
            f"qualidade: {resultado['qualidade_extracao']}"
        )

        doc_id = f"prodist-modulo-{modulo:02d}"
        url_blob = (
            f"{ANEEL_GITLAB_URL}/{ANEEL_GITLAB_PROJECT}" f"/-/blob/master/{pdf_path}"
        )

        documentos.append(
            montar_documento(
                id=doc_id,
                tipo="procedimento",
                subtipo="prodist",
                numero=f"Módulo {modulo}",
                ano=None,
                titulo=f"PRODIST — Módulo {modulo}",
                assunto="Procedimentos de Distribuição",
                situacao=None,
                data_publicacao=None,
                fonte="gitlab",
                url_original=url_blob,
                url_consolidado=None,
                formato_original="pdf",
                resultado=resultado,
                scraped_at=scraped_at,
            )
        )

    except Exception as e:
        print(f"    ❌ Erro: {e}")

    return documentos


# =========================================================================
# PRORET — Procedimentos de Regulação Tarifária
# =========================================================================
# Estrutura no GitLab (2026-06-01): procreg/proret/modulo02..modulo12
# com subpastas subm2.1, subm2.1A, etc. e PDFs em cada nível.


def _encontrar_pasta_proret() -> str | None:
    """Localiza a pasta PRORET na raiz do repositório GitLab."""
    try:
        itens_raiz = listar_arquivos_gitlab("")
    except Exception:
        return None

    for item in itens_raiz:
        if item["type"] != "tree":
            continue
        nome = item["name"].lower()
        if nome == "procreg" or "procreg" in item["path"].lower():
            try:
                sub = listar_arquivos_gitlab(item["path"])
                for s in sub:
                    if "proret" in s["name"].lower() and s["type"] == "tree":
                        return s["path"]
            except Exception:
                pass

    # Busca direta por path conhecido
    try:
        listar_arquivos_gitlab("procreg/proret")
        return "procreg/proret"
    except Exception:
        return None


def _listar_pdfs_recursivo(path: str) -> list[str]:
    """Lista paths de todos os PDFs sob uma pasta do GitLab."""
    pdfs: list[str] = []
    try:
        itens = listar_arquivos_gitlab(path)
    except Exception:
        return pdfs

    for item in itens:
        if item["type"] == "blob" and item["name"].lower().endswith(".pdf"):
            pdfs.append(item["path"])
        elif item["type"] == "tree":
            pdfs.extend(_listar_pdfs_recursivo(item["path"]))
            time.sleep(0.3)
    return pdfs


def _id_proret_de_path(gitlab_path: str) -> str:
    """Gera id estável a partir do path no GitLab (ex.: proret-modulo02-subm2-1)."""
    rel = gitlab_path.lower()
    if "procreg/proret/" in rel:
        rel = rel.split("procreg/proret/", 1)[1]
    slug = re.sub(r"[^a-z0-9]+", "-", rel.replace(".pdf", "")).strip("-")
    return f"proret-{slug}" if slug else "proret-documento"


def coletar_proret(estrategia: str = "texto") -> list[dict]:
    """
    Coleta todos os PDFs do PRORET no GitLab (módulos 2–12 e submódulos).

    A árvore é percorrida recursivamente — cada PDF vira um documento no schema.
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos: list[dict] = []

    print("Coletando PRORET (GitLab)...")
    proret_path = _encontrar_pasta_proret()
    if proret_path is None:
        print("  ❌ Pasta PRORET não encontrada no GitLab.")
        return []

    print(f"  ✅ PRORET em: {proret_path}")
    pdf_paths = _listar_pdfs_recursivo(proret_path)
    print(f"  {len(pdf_paths)} PDF(s) encontrados")

    for pdf_path in pdf_paths:
        doc_id = _id_proret_de_path(pdf_path)
        titulo = pdf_path.split("/")[-1].replace(".pdf", "").replace("_", " ")
        print(f"  {doc_id}: {pdf_path}")

        try:
            pdf_bytes = baixar_arquivo_gitlab(pdf_path, ref="main")
            resultado = extrair_texto(pdf_bytes, "pdf", formato_saida=estrategia)
            if len(resultado["texto"].strip()) < 100:
                print("    ⚠️  Texto curto — pulando")
                continue

            url_blob = (
                f"{ANEEL_GITLAB_URL}/{ANEEL_GITLAB_PROJECT}"
                f"/-/blob/main/{pdf_path}"
            )
            documentos.append(
                montar_documento(
                    id=doc_id,
                    tipo="procedimento",
                    subtipo="proret",
                    numero=titulo[:80],
                    ano=None,
                    titulo=f"PRORET — {titulo}",
                    assunto="Procedimentos de Regulação Tarifária",
                    situacao=None,
                    data_publicacao=None,
                    fonte="gitlab",
                    url_original=url_blob,
                    url_consolidado=None,
                    formato_original="pdf",
                    resultado=resultado,
                    scraped_at=scraped_at,
                )
            )
            print(f"    ✅ {len(resultado['texto'])} chars")
        except Exception as e:
            print(f"    ❌ Erro: {e}")

        time.sleep(1)

    print(f"\n✅ {len(documentos)} documentos PRORET coletados.")
    return documentos


# =========================================================================
# Regras de Transmissão (6 módulos)
# =========================================================================

# URLs diretas confirmadas via inspeção do portal gov.br (2026-05-30).
# Todos estão no GitLab da ANEEL em procreg/regtransm/.
_REGRAS_TRANSMISSAO_MODULOS = [
    {
        "modulo": 1,
        "titulo": "Regras de Transmissão — Módulo 1 — Glossário",
        "gitlab_path": "procreg/regtransm/Modulo 01_Glossario_aren2020905_2.pdf",
    },
    {
        "modulo": 2,
        "titulo": "Regras de Transmissão — Módulo 2 — Classificação das Instalações",
        "gitlab_path": "procreg/regtransm/Modulo 02_Classificacao Instalacoes_aren2020905_2_1.pdf",
    },
    {
        "modulo": 3,
        "titulo": "Regras de Transmissão — Módulo 3 — Instalações e Equipamentos",
        "gitlab_path": "procreg/regtransm/Modulo 03_Instalacoes_Equipamentos_aren2020905_2_2.pdf",
    },
    {
        "modulo": 4,
        "titulo": "Regras de Transmissão — Módulo 4 — Prestação dos Serviços",
        "gitlab_path": "procreg/regtransm/Modulo 04_Prestacao_Servicos_aren2020905_2_3.pdf",
    },
    {
        "modulo": 5,
        "titulo": "Regras de Transmissão — Módulo 5 — Acesso ao Sistema",
        "gitlab_path": "procreg/regtransm/Modulo 05_Acesso_Sistema_aren2020905_2_4.pdf",
    },
    {
        "modulo": 6,
        "titulo": "Regras de Transmissão — Módulo 6 — Coordenação e Controle da Operação",
        "gitlab_path": "procreg/regtransm/Modulo 06_Coordenacao_Controle_Opercao_aren2020905_2_5.pdf",
    },
]


def coletar_regras_transmissao(estrategia: str = "texto") -> list[dict]:
    """
    Coleta os 6 módulos das Regras de Transmissão do GitLab da ANEEL.

    Diferente do PRODIST, as Regras de Transmissão usam URLs diretas conhecidas
    (não precisam de navegação dinâmica pela árvore do GitLab). Isso é possível
    porque a página gov.br expõe os links raw diretamente.

    Returns:
        lista de dicts no formato do schema do corpus
    """

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos = []

    print("Coletando Regras de Transmissão (6 módulos)...")

    for mod in _REGRAS_TRANSMISSAO_MODULOS:
        modulo = mod["modulo"]
        titulo = mod["titulo"]
        gitlab_path = mod["gitlab_path"]
        doc_id = f"regtransm-modulo-{modulo:02d}"

        print(f"  Módulo {modulo}: {titulo}")

        try:
            pdf_bytes = baixar_arquivo_gitlab(gitlab_path, ref="main")
            print(f"    ✅ {len(pdf_bytes) / 1024:.0f} KB baixados")

            resultado = extrair_texto(pdf_bytes, "pdf", formato_saida=estrategia)
            print(
                f"    📄 {resultado['num_paginas']} págs | "
                f"{len(resultado['texto'])} chars | "
                f"qualidade: {resultado['qualidade_extracao']}"
            )

            url_blob = (
                f"{ANEEL_GITLAB_URL}/{ANEEL_GITLAB_PROJECT}"
                f"/-/blob/main/{gitlab_path}"
            )

            documentos.append(
                montar_documento(
                    id=doc_id,
                    tipo="procedimento",
                    subtipo="regras_transmissao",
                    numero=f"Módulo {modulo}",
                    ano=2020,
                    titulo=titulo,
                    assunto="Regras dos Serviços de Transmissão",
                    situacao=None,
                    data_publicacao=None,
                    fonte="gitlab",
                    url_original=url_blob,
                    url_consolidado=None,
                    formato_original="pdf",
                    resultado=resultado,
                    scraped_at=scraped_at,
                )
            )

        except Exception as e:
            print(f"    ❌ Erro: {e}")

        time.sleep(1)  # respeito ao servidor

    print(f"\n✅ {len(documentos)} módulos de Regras de Transmissão coletados.")
    return documentos
