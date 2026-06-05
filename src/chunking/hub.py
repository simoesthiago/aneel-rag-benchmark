"""Leitura de chunks publicados no HuggingFace Hub."""

from __future__ import annotations

import io
import os
import re

import pandas as pd
import requests
from huggingface_hub import HfApi, hf_hub_url

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

        df_part = _read_parquet_hub_sem_cache(repo_id, path)
        df_part["chunk_strategy"] = strategy
        df_part["metodo_extracao"] = metodo
        df_part["tipo"] = tipo
        partes.append(df_part)

    df = pd.concat(partes, ignore_index=True)
    print(f"  {len(df)} chunks no Hub")
    return df


def _read_parquet_hub_sem_cache(repo_id: str, path: str) -> pd.DataFrame:
    """Lê um Parquet do Hub em memória, sem gravar no cache local."""
    url = hf_hub_url(repo_id=repo_id, filename=path, repo_type="dataset")
    headers = {}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()
    return pd.read_parquet(io.BytesIO(response.content), engine="pyarrow")


def _extract_partition(path: str, name: str) -> str:
    match = re.search(rf"{name}=([^/]+)/", path)
    if match is None:
        raise RuntimeError(f"Parquet de chunks sem partição {name}=: {path}")
    return match.group(1)
