"""
run.py — Orquestrador do pipeline de ingestão por fonte e estratégia.

Por que este módulo existe?
---------------------------
Os scrapers são unidades isoladas por fonte de dados. Este módulo os conecta:
define quais coletar, com qual estratégia de extração, e publica no HF Hub com
merge incremental. Não há mais "waves" — o pipeline é incremental por natureza.

Fontes disponíveis:
    atos               → Power BI + cedoc/ (RENs e outros atos normativos)
    leis               → planalto.gov.br (4 leis estruturantes)
    procedimentos      → GitLab ANEEL (PRODIST, PRORET, Regras de Transmissão)
    procedimentos-rede → SharePoint ONS (Procedimentos de Rede)
    manuais            → gov.br (manuais, modelos e instruções)

Estratégias de extração de PDF (benchmark de ingestão):
    pymupdf   → PyMuPDF (baseline, rápido, PDFs nativos)
    docling   → Docling/IBM (IA layout detection, melhor em tabelas e scans)

Como usar:
    # Ingestão incremental de uma fonte
    python -m src.ingestion.run --fonte procedimentos-rede

    # Benchmark de extração (Docling na amostra de proc de rede)
    python -m src.ingestion.run --fonte procedimentos-rede --estrategia docling --amostra 10

    # Dry-run (valida schema, não sobe ao Hub)
    python -m src.ingestion.run --fonte leis --dry-run

    # Todas as fontes (ingestão completa)
    python -m src.ingestion.run --todas
"""

import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

from src.config.settings import HF_DATASET_REPO
from src.ingestion.scraper_atos import (
    coletar_atos,
    consultar_powerbi,
    filtrar_nao_vigentes,
    filtrar_vigentes,
)
from src.ingestion.scraper_leis import coletar_leis
from src.ingestion.scraper_manuais import coletar_manuais
from src.ingestion.scraper_procedimentos import (
    coletar_prodist_modulo,
    coletar_proret,
    coletar_regras_transmissao,
)
from src.ingestion.scraper_procedimentos_rede import coletar_procedimentos_rede
from src.ingestion.uploader import (
    carregar_corpus_hub,
    mesclar_corpus,
    publicar_corpus,
    validar_schema,
)

_FONTES_VALIDAS = {"atos", "leis", "procedimentos", "procedimentos-rede", "manuais"}


def _coletar_atos(estrategia: str, max_docs: int | None = None) -> list[dict]:
    print("\n=== Consultando Power BI (atos normativos) ===")
    todos = consultar_powerbi(["Resolução", "Situação", "Tipo", "Ementa", "Data"])
    vigentes = filtrar_vigentes(todos, sigla="ren")
    nao_vigentes = filtrar_nao_vigentes(todos, sigla="ren")
    todos_ren = vigentes + nao_vigentes
    print(f"  {len(todos_ren)} RENs no índice ({len(vigentes)} vigentes)")
    return coletar_atos(todos_ren, max_atos=max_docs, estrategia=estrategia)


def _coletar_procedimentos(estrategia: str) -> list[dict]:
    docs: list[dict] = []
    for m in range(1, 12):
        docs.extend(coletar_prodist_modulo(m, estrategia=estrategia))
    docs.extend(coletar_regras_transmissao(estrategia=estrategia))
    docs.extend(coletar_proret(estrategia=estrategia))
    return docs


def _coletar_fonte(
    fonte: str,
    estrategia: str,
    amostra: int | None,
) -> list[dict]:
    """Despacha para o(s) scraper(s) correto(s) e retorna docs coletados."""
    if fonte == "atos":
        return _coletar_atos(estrategia, max_docs=amostra)
    if fonte == "leis":
        # Leis são HTML — estratégia de PDF é ignorada silenciosamente.
        return coletar_leis()
    if fonte == "procedimentos":
        return _coletar_procedimentos(estrategia)
    if fonte == "procedimentos-rede":
        return coletar_procedimentos_rede(estrategia=estrategia)
    if fonte == "manuais":
        return coletar_manuais(max_manuais=amostra, estrategia=estrategia)
    raise ValueError(f"Fonte desconhecida: {fonte}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline de ingestão por fonte e estratégia"
    )
    parser.add_argument(
        "--fonte",
        action="append",
        choices=sorted(_FONTES_VALIDAS),
        metavar="FONTE",
        dest="fontes",
        help=(
            "Fonte a coletar (repetível). "
            f"Opções: {', '.join(sorted(_FONTES_VALIDAS))}"
        ),
    )
    parser.add_argument(
        "--todas",
        action="store_true",
        help="Coletar todas as fontes (equivale a --fonte para cada uma)",
    )
    parser.add_argument(
        "--estrategia",
        default="pymupdf",
        choices=["pymupdf", "pymupdf4llm"],
        help="Estratégia de extração de PDF (default: pymupdf)",
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=None,
        metavar="N",
        help="Limite de documentos por fonte (útil para benchmark e dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não faz upload no HF Hub (só valida o schema)",
    )
    parser.add_argument(
        "--sem-merge",
        action="store_true",
        help="Não mescla com o Hub (substitui o corpus inteiro)",
    )
    parser.add_argument(
        "--limpar-estrutura",
        action="store_true",
        help=(
            "Apaga data/ no Hub antes de subir (usar só na migração de estrutura, "
            "ex.: primeira vez que sobe com metodo_extracao= como partição)"
        ),
    )
    args = parser.parse_args()

    fontes = list(_FONTES_VALIDAS) if args.todas else (args.fontes or [])
    if not fontes:
        parser.error("Especifique pelo menos uma --fonte ou use --todas.")

    started_at = datetime.now(timezone.utc)
    print("==========================================================")
    print(f" ANEEL Corpus — ingestão ({started_at.isoformat()})")
    print(f" Fontes: {', '.join(fontes)}")
    print(f" Estratégia: {args.estrategia}")
    if args.amostra:
        print(f" Amostra: {args.amostra} docs/fonte")
    if args.dry_run:
        print(" Modo: dry-run (sem upload)")
    print("==========================================================")

    docs_novos: list[dict] = []
    erros: list[str] = []

    for fonte in fontes:
        print(f"\n→ Coletando: {fonte}")
        try:
            docs = _coletar_fonte(fonte, args.estrategia, args.amostra)
            print(f"  {len(docs)} documentos coletados")
            docs_novos.extend(docs)
        except Exception as e:
            erros.append(f"{fonte}: {e}")
            print(f"  ❌ FALHA — {e}")

    print("\n=== Consolidação ===")
    print(f"  Novos: {len(docs_novos)} documentos")
    if erros:
        print(f"  ⚠️  {len(erros)} fonte(s) com falha: {erros}")

    if not docs_novos:
        print("❌ Nada coletado. Abortando.")
        return 1

    df_novos = pd.DataFrame(docs_novos)

    mesclar = not args.sem_merge
    if mesclar and not args.dry_run:
        try:
            df_hub = carregar_corpus_hub()
            df_final = mesclar_corpus(df_hub, df_novos)
            print(f"  Após merge: {len(df_final)} documentos no total")
        except Exception as e:
            print(f"❌ Merge com Hub falhou: {e}")
            return 1
    else:
        df_final = df_novos

    validar_schema(df_final)
    print(f"  ✅ Schema validado ({len(df_final)} documentos)")

    if args.dry_run:
        print("\n[dry-run] Upload pulado.")
        return 0

    print(f"\n=== Upload para {HF_DATASET_REPO} ===")
    url = publicar_corpus(
        df_final,
        mesclar_com_hub=False,
        limpar_estrutura=args.limpar_estrutura,
    )
    print(f"\n✅ Concluído: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
