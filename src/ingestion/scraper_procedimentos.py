"""
scraper_procedimentos.py — Coleta de procedimentos regulatórios via GitLab.

Por que este módulo existe?
---------------------------
O PRODIST, PRORET e outros procedimentos regulatórios da ANEEL ficam num
GitLab público (git.aneel.gov.br/publico/centralconteudo). Este módulo
usa a API REST do GitLab para descobrir e baixar PDFs.

O GitLab não exige autenticação para projetos públicos.

Fontes:
    - PRODIST (11 módulos) — Procedimentos de Distribuição
    - PRORET — Procedimentos de Regulação Tarifária
    - Procedimentos de Rede
    - Regras de Eficiência Energética e P&D
    - Regras de Transmissão

Onde roda:
    Google Colab (API REST + download de PDFs + PyMuPDF)

Como usar:
    from src.ingestion.scraper_procedimentos import listar_arquivos_gitlab, coletar_prodist_modulo

    # Listar conteúdo de uma pasta
    itens = listar_arquivos_gitlab("PRODIST")

    # Coletar um módulo específico
    documentos = coletar_prodist_modulo(1)
"""

import time
import urllib.parse
from datetime import datetime, timezone

import requests

from src.config.settings import ANEEL_GITLAB_URL, ANEEL_GITLAB_PROJECT
from src.ingestion.extractor import extrair_texto


# Path do projeto URL-encoded (GitLab aceita path ou ID numérico)
_GITLAB_PROJECT_PATH = urllib.parse.quote(ANEEL_GITLAB_PROJECT, safe="")


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
        f"{ANEEL_GITLAB_URL}/api/v4/projects/"
        f"{_GITLAB_PROJECT_PATH}/repository/tree"
    )
    params = {"path": path, "per_page": 100}

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def baixar_arquivo_gitlab(file_path: str, ref: str = "master") -> bytes:
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

    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
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


def coletar_prodist_modulo(modulo: int) -> list[dict]:
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
    print(f"  Procurando PRODIST no GitLab...")
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
        print(f"    ❌ Pasta PRODIST não encontrada no GitLab.")
        return []

    print(f"    ✅ PRODIST encontrado em: {prodist_path}")

    # Listar módulos dentro do PRODIST
    prodist_itens = listar_arquivos_gitlab(prodist_path)

    # Procurar o módulo específico
    modulo_str = str(modulo)
    modulo_path = None
    for item in prodist_itens:
        nome_lower = item["name"].lower()
        # Procura variações: "Módulo 1", "Modulo 1", "módulo1", etc.
        if (
            f"módulo {modulo_str}" in nome_lower
            or f"modulo {modulo_str}" in nome_lower
            or f"módulo{modulo_str}" in nome_lower
            or f"modulo{modulo_str}" in nome_lower
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
        pdf_bytes = baixar_arquivo_gitlab(pdf_path)
        print(f"    ✅ {len(pdf_bytes) / 1024:.0f} KB baixados")

        resultado = extrair_texto(pdf_bytes, "pdf")
        print(
            f"    📄 {resultado['num_paginas']} págs | "
            f"{len(resultado['texto'])} chars | "
            f"qualidade: {resultado['qualidade_extracao']}"
        )

        doc_id = f"prodist-modulo-{modulo:02d}"
        url_blob = (
            f"{ANEEL_GITLAB_URL}/{ANEEL_GITLAB_PROJECT}"
            f"/-/blob/master/{pdf_path}"
        )

        documentos.append({
            "id": doc_id,
            "tipo": "procedimento",
            "subtipo": "prodist",
            "numero": f"Módulo {modulo}",
            "ano": None,  # PRODIST é atualizado continuamente
            "titulo": f"PRODIST — Módulo {modulo}",
            "assunto": "Procedimentos de Distribuição",
            "situacao": None,
            "data_publicacao": None,
            "fonte": "gitlab",
            "url_original": url_blob,
            "url_consolidado": None,
            "formato_original": "pdf",
            "texto_bruto": resultado["texto"],
            "num_paginas": resultado["num_paginas"],
            "metodo_extracao": resultado["metodo"],
            "qualidade_extracao": resultado["qualidade_extracao"],
            "hf_path": None,
            "scraped_at": scraped_at,
        })

    except Exception as e:
        print(f"    ❌ Erro: {e}")

    return documentos
