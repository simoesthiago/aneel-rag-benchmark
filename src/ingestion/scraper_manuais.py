"""
scraper_manuais.py — Coleta de Manuais, Modelos e Instruções (gov.br).

Por que este módulo existe?
---------------------------
A central de conteúdos da ANEEL lista dezenas de manuais por área temática.
Os arquivos costumam estar no GitLab (`manuaisminstrucoes/`) ou em links
diretos para PDF/DOCX/XLSX nas páginas gov.br.

Este scraper percorre as subcategorias configuradas em `MANUAIS_SUBCATEGORIAS`,
extrai links de download e publica no schema como `tipo="manual"`.

Onde roda:
    Máquina local (HTTP para gov.br e GitLab).

Como usar:
    from src.ingestion.scraper_manuais import coletar_manuais
    documentos = coletar_manuais()
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import warnings

import requests
import urllib3
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

# git.aneel.gov.br usa certificado intermediário não reconhecido pelo Python/macOS.
# Suprimimos o aviso para não poluir o output do pipeline.
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

# Domínios que exigem curl_cffi (Cloudflare TLS fingerprinting).
_CFFI_HOSTS = {"www2.aneel.gov.br"}

from src.config.settings import ANEEL_MANUAIS_URL, MANUAIS_SUBCATEGORIAS
from src.ingestion.extractors import extrair_texto
from src.ingestion.schema import montar_documento

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
_REQUEST_TIMEOUT_S = 90
_SLEEP_ENTRE_DOWNLOADS_S = 1.0

# Atos do cedoc/ já são coletados por scraper_atos — não duplicar como manual.
_CEDOC_REN_PATTERN = re.compile(r"/cedoc/ren\d+\.pdf", re.I)


def _slugify(texto: str) -> str:
    """Converte texto em slug ASCII para IDs."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower()).strip("-")
    return texto[:80] or "documento"


def listar_subcategorias() -> list[str]:
    """Retorna paths relativos das subcategorias (config em settings)."""
    return list(MANUAIS_SUBCATEGORIAS)


def _url_subcategoria(slug: str) -> str:
    base = ANEEL_MANUAIS_URL.rstrip("/")
    return f"{base}/{slug}"


def _extrair_links_arquivos(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """
    Encontra links para PDF/DOCX/XLSX na página.

    Returns:
        lista de (titulo, url_absoluta, formato)
    """
    soup = BeautifulSoup(html, "lxml")
    encontrados: list[tuple[str, str, str]] = []
    vistos: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        url_abs = urljoin(base_url, href)
        if url_abs in vistos:
            continue
        lower = url_abs.lower().split("?")[0]
        formato = None
        if lower.endswith(".pdf"):
            formato = "pdf"
        elif lower.endswith(".docx") or lower.endswith(".doc"):
            formato = "docx" if lower.endswith(".docx") else "docx"
        elif lower.endswith(".xlsx") or lower.endswith(".xls"):
            formato = "xlsx" if lower.endswith(".xlsx") else "xlsx"
        else:
            continue

        if _CEDOC_REN_PATTERN.search(url_abs):
            continue

        titulo = a.get_text(strip=True) or url_abs.split("/")[-1]
        vistos.add(url_abs)
        encontrados.append((titulo, url_abs, formato))

    return encontrados


def _baixar_url(url: str) -> bytes:
    """
    Baixa um arquivo de URL.

    www2.aneel.gov.br usa Cloudflare TLS fingerprinting — requests puro recebe 403.
    Para esse domínio, usamos curl_cffi com impersonate="chrome120" (mesmo método
    do scraper_atos.py para o cedoc/).

    Para outros domínios (git.aneel.gov.br, gov.br etc.), usamos requests normal
    com verify=False para contornar o certificado intermediário do GitLab ANEEL.
    """
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if host in _CFFI_HOSTS:
        resp = cffi_requests.get(url, impersonate="chrome120", timeout=_REQUEST_TIMEOUT_S)
    else:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT_S, verify=False)
    resp.raise_for_status()
    return resp.content


def coletar_manuais(
    subcategorias: list[str] | None = None,
    max_manuais: int | None = None,
    estrategia: str = "pymupdf",
) -> list[dict]:
    """
    Coleta manuais de todas as subcategorias do portal gov.br.

    Args:
        subcategorias: lista de slugs; default = MANUAIS_SUBCATEGORIAS
        max_manuais: limite total de documentos (útil em dry-run/dev)

    Returns:
        lista de dicts no formato do schema
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slugs = subcategorias or listar_subcategorias()
    documentos: list[dict] = []
    ids_vistos: set[str] = set()

    print(f"Coletando manuais ({len(slugs)} subcategorias)...")

    for slug in slugs:
        if max_manuais is not None and len(documentos) >= max_manuais:
            break

        url_pagina = _url_subcategoria(slug)
        print(f"\n  Área: {slug}")
        try:
            resp = requests.get(url_pagina, headers=_HEADERS, timeout=_REQUEST_TIMEOUT_S)
            resp.raise_for_status()
        except Exception as e:
            print(f"    ❌ Falha ao abrir página: {e}")
            continue

        links = _extrair_links_arquivos(resp.text, url_pagina)
        print(f"    {len(links)} arquivo(s) encontrado(s)")

        for titulo, url_arquivo, formato in links:
            if max_manuais is not None and len(documentos) >= max_manuais:
                break

            base_id = f"manual-{_slugify(slug)}-{_slugify(titulo)}"
            doc_id = base_id
            sufixo = 2
            while doc_id in ids_vistos:
                doc_id = f"{base_id}-{sufixo}"
                sufixo += 1

            print(f"    → {doc_id} ({formato})")

            try:
                conteudo = _baixar_url(url_arquivo)
                # HTML não tem estratégia alternativa — ignora o parâmetro.
                ext = estrategia if formato == "pdf" else None
                resultado = extrair_texto(conteudo, formato, estrategia=ext)
                if len(resultado["texto"].strip()) < 100:
                    print("      ⚠️  Texto < 100 chars — pulando")
                    continue

                area_nome = slug.split("/")[0].replace("-", " ").title()
                doc = montar_documento(
                    id=doc_id,
                    tipo="manual",
                    subtipo=slug.split("/")[0],
                    numero=None,
                    ano=None,
                    titulo=titulo[:500] if titulo else doc_id,
                    assunto=area_nome,
                    situacao=None,
                    data_publicacao=None,
                    fonte="gov_br",
                    url_original=url_arquivo,
                    url_consolidado=None,
                    formato_original=formato,
                    resultado=resultado,
                    scraped_at=scraped_at,
                )
                documentos.append(doc)
                ids_vistos.add(doc_id)
                print(f"      ✅ {len(resultado['texto'])} chars")
            except Exception as e:
                print(f"      ❌ Erro: {e}")

            time.sleep(_SLEEP_ENTRE_DOWNLOADS_S)

        time.sleep(0.5)

    print(f"\n✅ {len(documentos)} manuais coletados.")
    return documentos
