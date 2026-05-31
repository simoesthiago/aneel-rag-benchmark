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
    4. Procedimentos de Rede → FORA DO ESCOPO (pertencem ao ONS, não à ANEEL)
    5. EE/P&D (PROPEE + PROPDI) → FORA DO ESCOPO (são RENs, já cobertas por scraper_atos.py)

Este scraper cobre as subcategorias 1, 2 e 3 — todas no mesmo GitLab.

Onde roda:
    Google Colab (API REST + download de PDFs + PyMuPDF)

Como usar:
    from src.ingestion.scraper_procedimentos import (
        listar_arquivos_gitlab,
        coletar_prodist_modulo,
        coletar_regras_transmissao,
    )

    documentos = coletar_prodist_modulo(1)
    documentos += coletar_regras_transmissao()
"""

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
        f"{ANEEL_GITLAB_URL}/api/v4/projects/" f"{_GITLAB_PROJECT_PATH}/repository/tree"
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
            f"{ANEEL_GITLAB_URL}/{ANEEL_GITLAB_PROJECT}" f"/-/blob/master/{pdf_path}"
        )

        documentos.append(
            {
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
            }
        )

    except Exception as e:
        print(f"    ❌ Erro: {e}")

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


def coletar_regras_transmissao() -> list[dict]:
    """
    Coleta os 6 módulos das Regras de Transmissão do GitLab da ANEEL.

    Diferente do PRODIST, as Regras de Transmissão usam URLs diretas conhecidas
    (não precisam de navegação dinâmica pela árvore do GitLab). Isso é possível
    porque a página gov.br expõe os links raw diretamente.

    Returns:
        lista de dicts no formato do schema do corpus
    """
    import time

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

            resultado = extrair_texto(pdf_bytes, "pdf")
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
                {
                    "id": doc_id,
                    "tipo": "procedimento",
                    "subtipo": "regras_transmissao",
                    "numero": f"Módulo {modulo}",
                    "ano": 2020,  # REN 905/2020 aprovou a estrutura
                    "titulo": titulo,
                    "assunto": "Regras dos Serviços de Transmissão",
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
                }
            )

        except Exception as e:
            print(f"    ❌ Erro: {e}")

        time.sleep(1)  # respeito ao servidor

    print(f"\n✅ {len(documentos)} módulos de Regras de Transmissão coletados.")
    return documentos
