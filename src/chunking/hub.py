"""Leitura de chunks publicados no HuggingFace Hub."""

from __future__ import annotations

import re

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

from src.config.settings import HF_DATASET_REPO


def carregar_chunks_hub(repo_id: str | None = None) -> pd.DataFrame:
    """
    Carrega `data/chunks/` publicado no HuggingFace Hub.

    O uploader de chunks remove as colunas de partição do Parquet. Este loader
    restaura `chunk_strategy`, `metodo_extracao` e `tipo` a partir do path.
    """
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    print(f"  Carregando chunks de {repo_id}...")
    api = HfApi()
    arquivos = api.list_repo_files(repo_id, repo_type="dataset")
    parquets = sorted(
        path
        for path in arquivos
        if path.startswith("data/chunks/") and path.endswith(".parquet")
    )
    if not parquets:
        raise RuntimeError(
            f"Nenhum Parquet de chunks encontrado em {repo_id}. "
            "Publique chunks com `python -m src.chunking.run --publicar`."
        )

    partes: list[pd.DataFrame] = []
    for path in parquets:
        strategy = _extract_partition(path, "chunk_strategy")
        metodo = _extract_partition(path, "metodo_extracao")
        tipo = _extract_partition(path, "tipo")

        local = hf_hub_download(
            repo_id=repo_id, filename=path, repo_type="dataset"
        )
        df_part = pd.read_parquet(local, engine="pyarrow")
        df_part["chunk_strategy"] = strategy
        df_part["metodo_extracao"] = metodo
        df_part["tipo"] = tipo
        partes.append(df_part)

    df = pd.concat(partes, ignore_index=True)
    print(f"  {len(df)} chunks no Hub")
    return df


def _extract_partition(path: str, name: str) -> str:
    match = re.search(rf"{name}=([^/]+)/", path)
    if match is None:
        raise RuntimeError(f"Parquet de chunks sem partição {name}=: {path}")
    return match.group(1)
