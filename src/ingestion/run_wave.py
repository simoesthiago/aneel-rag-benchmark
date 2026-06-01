"""
run_wave.py — Orquestrador do pipeline de ingestão por wave.

Por que este módulo existe?
---------------------------
Os scrapers (`scraper_atos`, `scraper_leis`, `scraper_procedimentos`,
`scraper_manuais`) são unidades isoladas. Este módulo amarra tudo: define o
escopo de cada Wave, chama os scrapers na ordem correta, consolida no schema,
valida e publica no HuggingFace Hub.

Roda na máquina local (IP residencial brasileiro para o cedoc/) com
`HF_TOKEN` no `.env` para publicar no HuggingFace Hub.

Como usar:
    python -m src.ingestion.run_wave --wave 1
    python -m src.ingestion.run_wave --wave 3 --mesclar-com-hub
"""

import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

from src.config.settings import HF_DATASET_REPO
from src.ingestion.scraper_atos import (
    consultar_powerbi,
    coletar_atos,
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
from src.ingestion.uploader import (
    carregar_corpus_hub,
    mesclar_corpus,
    publicar_corpus,
    validar_schema,
)

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


def _coletar_atos_wave(wave: int, max_atos: int | None = None) -> list[dict]:
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
    else:  # wave 3 — incremental: só não vigentes
        selecionadas = filtrar_nao_vigentes(todos, sigla="ren")
        print(f"  Wave 3: {len(selecionadas)} RENs não vigentes (revogadas)")

    return coletar_atos(selecionadas, max_atos=max_atos)


def _coletar_procedimentos_wave(wave: int) -> list[dict]:
    """Coleta procedimentos regulatórios conforme a wave."""
    docs: list[dict] = []
    if wave == 1:
        docs.extend(coletar_prodist_modulo(1))
    elif wave == 2:
        for m in range(1, 12):
            docs.extend(coletar_prodist_modulo(m))
        docs.extend(coletar_regras_transmissao())
    else:  # wave 3 — só PRORET (PRODIST/RegTransm já na Wave 2)
        docs.extend(coletar_proret())
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de ingestão por wave")
    parser.add_argument(
        "--wave",
        type=int,
        choices=[1, 2, 3],
        required=True,
        help=(
            "Wave: 1=amostra (~15 docs), 2=vigentes+PRODIST+RegTransm (~220), "
            "3=revogadas+PRORET+manuais (merge com Hub)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não faz upload no HF Hub (só valida o schema)",
    )
    parser.add_argument(
        "--mesclar-com-hub",
        action="store_true",
        help="Mescla com corpus existente no HF Hub antes do upload (Wave 3)",
    )
    parser.add_argument(
        "--sem-merge",
        action="store_true",
        help="Não mescla com o Hub mesmo na Wave 3 (substitui corpus inteiro)",
    )
    parser.add_argument(
        "--max-atos",
        type=int,
        default=None,
        help="Limita quantidade de atos baixados (dev/teste)",
    )
    parser.add_argument(
        "--max-manuais",
        type=int,
        default=None,
        help="Limita quantidade de manuais coletados (dev/teste)",
    )
    parser.add_argument(
        "--pular-leis",
        action="store_true",
        help="Não re-coleta as 4 leis (útil na Wave 3 com merge)",
    )
    args = parser.parse_args()

    mesclar = args.mesclar_com_hub or (args.wave == 3 and not args.sem_merge)

    started_at = datetime.now(timezone.utc)
    print("==========================================================")
    print(f" ANEEL Corpus — Wave {args.wave} (started {started_at.isoformat()})")
    if mesclar:
        print(" Modo: merge com corpus existente no HF Hub")
    print("==========================================================")

    erros_fonte: list[str] = []
    docs_leis: list[dict] = []

    if args.pular_leis or args.wave == 3:
        print("\n→ Leis: puladas (já no Hub ou --pular-leis)")
    else:
        try:
            docs_leis = coletar_leis()
            print(f"\n→ Leis: {len(docs_leis)} documentos")
        except Exception as e:
            erros_fonte.append(f"Leis: {e}")
            print(f"\n→ Leis: ❌ FALHA — {e}")

    try:
        docs_atos = _coletar_atos_wave(args.wave, max_atos=args.max_atos)
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

    docs_manuais: list[dict] = []
    if args.wave == 3:
        try:
            docs_manuais = coletar_manuais(max_manuais=args.max_manuais)
            print(f"\n→ Manuais: {len(docs_manuais)} documentos")
        except Exception as e:
            erros_fonte.append(f"Manuais: {e}")
            print(f"\n→ Manuais: ❌ FALHA — {e}")

    docs_novos = docs_leis + docs_atos + docs_proc + docs_manuais
    print("\n=== Consolidação (coleta desta execução) ===")
    print(f"  NOVOS: {len(docs_novos)} documentos")
    if erros_fonte:
        print(f"  ⚠️  {len(erros_fonte)} fonte(s) com falha:")
        for err in erros_fonte:
            print(f"    - {err}")

    if not docs_novos and not mesclar:
        print("❌ Nada coletado. Abortando.")
        return 1

    if mesclar and not args.dry_run:
        try:
            df_hub = carregar_corpus_hub()
            df = mesclar_corpus(df_hub, pd.DataFrame(docs_novos))
        except Exception as e:
            print(f"❌ Merge com Hub falhou: {e}")
            return 1
    elif mesclar and args.dry_run:
        print("\n[dry-run] Simulando merge: apenas validando documentos novos")
        df = pd.DataFrame(docs_novos)
    else:
        df = pd.DataFrame(docs_novos)

    if df.empty:
        print("❌ DataFrame vazio após consolidação. Abortando.")
        return 1

    validar_schema(df)
    print(f"  ✅ Schema validado ({len(df)} documentos no corpus final)")

    if args.dry_run:
        print("\n[dry-run] Pulando upload para HF Hub")
        return 0

    print(f"\n=== Upload para {HF_DATASET_REPO} ===")
    url = publicar_corpus(df, mesclar_com_hub=False)
    print(f"\n✅ Pipeline concluído: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
