#!/usr/bin/env python3
"""Valida a matriz completa de vector stores publicada no HuggingFace Hub.

Este gate é propositalmente leve: ele não baixa `index.faiss`, porque cada
índice pode ter centenas de MB/GB. Em vez disso, confirma a presença do índice
no Hub e valida `manifest.json`, `metadata.parquet` e `parents.parquet` em
memória, sem cache local.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.vectorstore.hub import carregar_vectorstore_metadata_hub  # noqa: E402
from src.vectorstore.metadata import validar_vectorstore  # noqa: E402

MODELS = ["text-embedding-3-large", "text-embedding-3-small"]
STRATEGIES = ["fixed-size", "article-aware", "hierarchical-child"]
METODOS = ["markdown", "texto"]


def main() -> int:
    """Executa o gate leve nas 12 combinações da Camada 2.3."""
    failures: list[str] = []
    total = 0

    for model in MODELS:
        for strategy in STRATEGIES:
            for metodo in METODOS:
                total += 1
                label = f"openai / {model} / {strategy} / {metodo}"
                try:
                    pkg = carregar_vectorstore_metadata_hub(
                        provider="openai",
                        model=model,
                        chunk_strategy=strategy,
                        metodo_extracao=metodo,
                        repo_id=HF_DATASET_REPO,
                    )
                    manifest = pkg["manifest"]
                    metadata = pkg["metadata"]
                    parents = pkg["parents"]
                    _validar_manifest_esperado(
                        manifest,
                        model=model,
                        strategy=strategy,
                        metodo=metodo,
                    )
                    validar_vectorstore(
                        ntotal=int(manifest["count"]),
                        dimension=int(manifest["dimension"]),
                        metadata=metadata,
                        manifest=manifest,
                        parents=parents,
                    )
                except Exception as exc:  # noqa: BLE001 - gate deve listar todas
                    failures.append(f"{label}: {exc}")
                    print(f"❌ {label}")
                    print(f"   {exc}")
                else:
                    print(
                        f"✅ {label} | chunks={manifest['count']} "
                        f"dim={manifest['dimension']}"
                    )

    if failures:
        print(f"\n❌ {len(failures)}/{total} vector stores falharam:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"\n✅ Matriz completa validada: {total}/{total} vector stores.")
    print("   Gate leve: index.faiss presente; metadata/manifest/parents validados.")
    return 0


def _validar_manifest_esperado(
    manifest: dict,
    *,
    model: str,
    strategy: str,
    metodo: str,
) -> None:
    if manifest.get("provider") != "openai":
        raise RuntimeError(f"provider inesperado: {manifest.get('provider')!r}")
    if manifest.get("model") != model:
        raise RuntimeError(f"model inesperado: {manifest.get('model')!r}")
    if manifest.get("chunk_strategy") != strategy:
        raise RuntimeError(
            f"chunk_strategy inesperado: {manifest.get('chunk_strategy')!r}"
        )
    if manifest.get("metodo_extracao") != metodo:
        raise RuntimeError(
            f"metodo_extracao inesperado: {manifest.get('metodo_extracao')!r}"
        )


if __name__ == "__main__":
    sys.exit(main())
