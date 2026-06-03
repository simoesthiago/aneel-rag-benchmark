#!/usr/bin/env python3
"""
Valida o corpus publicado no HuggingFace Hub (gate antes da Wave 3).

Uso:
    python scripts/validate_corpus.py
    python scripts/validate_corpus.py --repo outro-usuario/outro-corpus
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como `python scripts/validate_corpus.py` na raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config.settings import HF_DATASET_REPO
from src.ingestion.uploader import carregar_corpus_hub

METODOS_ESPERADOS = frozenset({"texto", "markdown"})


def encontrar_ids_assimetricos(df: pd.DataFrame) -> list[dict[str, object]]:
    """
    Lista documentos que não têm as duas estratégias de extração.

    O benchmark compara texto vs. Markdown downstream. Se um documento existe em
    apenas uma estratégia, ele enviesaria chunking, embeddings e métricas de RAG.
    """
    if "metodo_extracao" not in df.columns:
        return []

    problemas: list[dict[str, object]] = []
    for doc_id, grupo in df.groupby("id", sort=True):
        presentes = set(grupo["metodo_extracao"].dropna().astype(str))
        faltantes = METODOS_ESPERADOS - presentes
        if faltantes:
            problemas.append(
                {
                    "id": doc_id,
                    "presente": sorted(presentes),
                    "faltante": sorted(faltantes),
                }
            )
    return problemas


def validar_corpus(repo_id: str) -> int:
    """Carrega o dataset e imprime métricas de qualidade. Retorna 0 se OK."""
    print(f"Carregando {repo_id}...")
    df: pd.DataFrame = carregar_corpus_hub(repo_id)

    print(f"\nTOTAL: {len(df)} documentos")
    print("\nPor tipo:")
    print(df["tipo"].value_counts().to_string())

    if "metodo_extracao" in df.columns:
        print("\nPor formato de saída (metodo_extracao):")
        print(df["metodo_extracao"].value_counts().to_string())

    if "extrator" in df.columns:
        print("\nPor ferramenta (extrator):")
        print(df["extrator"].value_counts().to_string())

    dup = int(df.duplicated(subset=["id", "metodo_extracao"]).sum())
    print(f"\nPares (id, metodo_extracao) duplicados: {dup}")

    assimetricos = encontrar_ids_assimetricos(df)
    print(f"IDs sem par texto/markdown: {len(assimetricos)}")
    if assimetricos:
        print("  Amostra:")
        for item in assimetricos[:20]:
            print(
                f"  - {item['id']} | presente={item['presente']} "
                f"| faltante={item['faltante']}"
            )

    curtos = df[df["texto_bruto"].str.len() < 100]
    print(f"texto_bruto < 100 chars: {len(curtos)}")
    if len(curtos):
        print("  IDs:", curtos["id"].tolist()[:20])

    if "qualidade_extracao" in df.columns:
        baixa = df[df["qualidade_extracao"].notna() & (df["qualidade_extracao"] < 0.5)]
        print(f"\nqualidade_extracao < 0.5: {len(baixa)}")
        if len(baixa):
            print(baixa[["id", "qualidade_extracao"]].head(15).to_string())

    erros = dup + len(assimetricos) + len(curtos)
    if erros:
        print("\n❌ Validação falhou.")
        return 1
    print("\n✅ Validação básica OK.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida corpus no HF Hub")
    parser.add_argument("--repo", default=HF_DATASET_REPO)
    args = parser.parse_args()
    return validar_corpus(args.repo)


if __name__ == "__main__":
    sys.exit(main())
