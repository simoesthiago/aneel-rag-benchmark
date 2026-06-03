"""
scraper_leis.py — Coleta das 4 leis estruturantes do setor elétrico.

Por que este módulo existe?
---------------------------
O corpus da ANEEL inclui as 4 leis de base que fundamentam toda a regulação
do setor elétrico. São HTML estático no site do Planalto — a fonte mais
simples do projeto, ideal como primeiro scraper de produção.

Fontes:
    - Lei 9.427/1996 — Criação da ANEEL
    - Lei 8.987/1995 — Concessões de Serviços Públicos
    - Lei 9.074/1995 — Outorgas e Prorrogações de Concessões
    - Lei 13.848/2019 — Lei das Agências Reguladoras

Como usar:
    from src.ingestion.scraper_leis import coletar_leis

    documentos = coletar_leis()
    # documentos = [{"id": "lei-9427-1996", "tipo": "lei", ...}, ...]
"""

import time
from datetime import datetime, timezone

import requests

from src.config.settings import LEIS_ESTRUTURANTES
from src.ingestion.extractors import extrair_texto
from src.ingestion.schema import montar_documento

# Headers HTTP — identificação como navegador para evitar bloqueios
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Metadados estáticos das 4 leis (não mudam — são leis federais consolidadas)
_LEIS_METADATA: dict[str, dict] = {
    "lei-9427-1996": {
        "titulo": "Lei 9.427/1996 — Criação da ANEEL",
        "numero": "9427",
        "ano": 1996,
    },
    "lei-8987-1995": {
        "titulo": "Lei 8.987/1995 — Concessões de Serviços Públicos",
        "numero": "8987",
        "ano": 1995,
    },
    "lei-9074-1995": {
        "titulo": "Lei 9.074/1995 — Outorgas e Prorrogações de Concessões",
        "numero": "9074",
        "ano": 1995,
    },
    "lei-13848-2019": {
        "titulo": "Lei 13.848/2019 — Lei das Agências Reguladoras",
        "numero": "13848",
        "ano": 2019,
    },
}


def coletar_leis(estrategia: str = "texto") -> list[dict]:
    """
    Coleta as 4 leis estruturantes do planalto.gov.br.

    Faz GET em cada URL, extrai o texto via dispatcher, e retorna uma lista
    de dicts no formato do schema do corpus (ver docs/schema.md).

    Args:
        estrategia: formato de saída ("texto" ou "markdown"). "texto" usa
            BeautifulSoup; "markdown" usa html2text. Ver `extractors/__init__.py`.

    Returns:
        lista de dicts, um por lei coletada com sucesso.
        Leis que falharem são logadas mas não interrompem a execução.
    """
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos = []

    for lei_id, url in LEIS_ESTRUTURANTES.items():
        meta = _LEIS_METADATA[lei_id]
        print(f"  Coletando {lei_id}...")

        try:
            # Baixar HTML da lei
            resp = requests.get(url, headers=_HEADERS, timeout=30)
            resp.raise_for_status()

            # Tratar encoding — Planalto pode usar ISO-8859-1
            if resp.encoding and "iso" in resp.encoding.lower():
                resp.encoding = resp.apparent_encoding or "utf-8"

            # Extrair texto usando o extractor centralizado
            resultado = extrair_texto(resp.text, "html", formato_saida=estrategia)

            print(
                f"    OK: {resultado['qualidade_extracao']} qualidade, "
                f"{len(resultado['texto'])} chars"
            )

            documentos.append(
                montar_documento(
                    id=lei_id,
                    tipo="lei",
                    subtipo="lei_federal",
                    numero=meta["numero"],
                    ano=meta["ano"],
                    titulo=meta["titulo"],
                    assunto=None,
                    situacao=None,
                    data_publicacao=None,
                    fonte="planalto",
                    url_original=url,
                    url_consolidado=None,
                    formato_original="html",
                    resultado=resultado,
                    scraped_at=scraped_at,
                )
            )

        except Exception as e:
            # Não queremos que 1 lei falhando trave as outras 3
            print(f"    ERRO: {e}")

        # Respeito ao servidor — 1 segundo entre requisições
        time.sleep(1)

    return documentos
