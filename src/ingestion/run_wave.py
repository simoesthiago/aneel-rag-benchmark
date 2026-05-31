"""
run_wave.py — Orquestrador do pipeline de ingestão por wave.

Por que este módulo existe?
---------------------------
Os scrapers (`scraper_atos`, `scraper_leis`, `scraper_procedimentos`) são
unidades isoladas. Este módulo amarra tudo: define o escopo de cada Wave,
chama os scrapers na ordem correta, consolida no schema, valida e publica
no HuggingFace Hub.

Roda em GitHub Actions (workflow `ingest_corpus.yml`) e também pode rodar
no Colab ou local desde que HF_TOKEN esteja configurado.

Como usar:
    python -m src.ingestion.run_wave --wave 1
"""

import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

from src.config.settings import HF_DATASET_REPO
from src.ingestion.scraper_atos import (
    consultar_powerbi,
    filtrar_vigentes,
    coletar_atos,
)
from src.ingestion.scraper_leis import coletar_leis
from src.ingestion.scraper_procedimentos import (
    coletar_prodist_modulo,
    coletar_regras_transmissao,
)
from src.ingestion.uploader import publicar_corpus, validar_schema

# RENs selecionadas para a Wave 1 — variedade temática controlada
RENS_WAVE1 = {
    "REN 1000/2021",
    "REN 1001/2022",
    "REN 1003/2022",
    "REN 1009/2022",
    "REN 1012/2022",
    "REN 1059/2023",
    "REN 482/2012",
    "REN 414/2010",
    "REN 875/2020",
    "REN 956/2021",
}


def _coletar_atos_wave(wave: int) -> list[dict]:
    """Lista atos do Power BI e filtra conforme a wave."""
    print(f"\n=== Consultando Power BI (Wave {wave}) ===")
    todos = consultar_powerbi(
        ["Resolução", "Situação", "Tipo", "Ementa", "Data"]
    )
    print(f"  {len(todos)} atos no índice")

    vigentes = filtrar_vigentes(todos, sigla="ren")
    print(f"  {len(vigentes)} RENs vigentes")

    if wave == 1:
        selecionadas = [a for a in vigentes if a.get("Resolução") in RENS_WAVE1]
        print(f"  Wave 1: {len(selecionadas)} RENs selecionadas (curadoria fixa)")
    elif wave == 2:
        selecionadas = vigentes
        print(f"  Wave 2: todas as {len(selecionadas)} RENs vigentes")
    else:  # wave 3
        selecionadas = [a for a in todos if a.get("Resolução", "").startswith("REN ")]
        print(f"  Wave 3: todos os {len(selecionadas)} atos (vigentes + revogados)")

    return coletar_atos(selecionadas)


def _coletar_procedimentos_wave(wave: int) -> list[dict]:
    """Coleta módulos PRODIST e Regras de Transmissão por wave."""
    docs = []
    if wave == 1:
        docs.extend(coletar_prodist_modulo(1))
    elif wave == 2:
        for m in range(1, 12):  # 11 módulos
            docs.extend(coletar_prodist_modulo(m))
        docs.extend(coletar_regras_transmissao())
    else:  # wave 3 — futuro: PRORET completo + manuais
        for m in range(1, 12):
            docs.extend(coletar_prodist_modulo(m))
        docs.extend(coletar_regras_transmissao())
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de ingestão por wave")
    parser.add_argument(
        "--wave", type=int, choices=[1, 2, 3], required=True,
        help="Wave a executar (1=mínima/~15 docs, 2=vigentes/~220 docs, 3=completa)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Não faz upload no HF Hub (só valida o schema)",
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)
    print(f"==========================================================")
    print(f" ANEEL Corpus — Wave {args.wave} (started {started_at.isoformat()})")
    print(f"==========================================================")

    # Coleta de cada fonte — independentes, falha parcial é aceitável.
    # O pipeline publica o que conseguir coletar.
    erros_fonte = []

    try:
        docs_leis = coletar_leis()
        print(f"\n→ Leis: {len(docs_leis)} documentos")
    except Exception as e:
        docs_leis = []
        erros_fonte.append(f"Leis: {e}")
        print(f"\n→ Leis: ❌ FALHA — {e}")

    try:
        docs_atos = _coletar_atos_wave(args.wave)
        print(f"\n→ Atos normativos: {len(docs_atos)} documentos")
    except Exception as e:
        docs_atos = []
        erros_fonte.append(f"Atos: {e}")
        print(f"\n→ Atos normativos: ❌ FALHA — {e}")

    try:
        docs_proc = _coletar_procedimentos_wave(args.wave)
        print(f"\n→ Procedimentos regulatórios: {len(docs_proc)} documentos")
    except Exception as e:
        docs_proc = []
        erros_fonte.append(f"Procedimentos: {e}")
        print(f"\n→ Procedimentos regulatórios: ❌ FALHA — {e}")

    todos = docs_leis + docs_atos + docs_proc
    print(f"\n=== Consolidação ===")
    print(f"  TOTAL: {len(todos)} documentos")
    if erros_fonte:
        print(f"  ⚠️  {len(erros_fonte)} fonte(s) com falha:")
        for err in erros_fonte:
            print(f"    - {err}")

    if not todos:
        print("❌ Nada coletado. Abortando.")
        return 1

    df = pd.DataFrame(todos)
    validar_schema(df)
    print("  ✅ Schema validado")

    if args.dry_run:
        print("\n[dry-run] Pulando upload para HF Hub")
        return 0

    print(f"\n=== Upload para {HF_DATASET_REPO} ===")
    url = publicar_corpus(df)
    print(f"\n✅ Pipeline concluído: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
