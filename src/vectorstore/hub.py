"""Publicação e leitura das vector stores FAISS no HuggingFace Hub.

Layout (Hive-style, consistente com `data/chunks/`):

    data/vectorstores/
      provider=openai/
        model=text-embedding-3-large/
          chunk_strategy=article-aware/
            metodo_extracao=markdown/
              index.faiss
              metadata.parquet
              manifest.json
              (parents.parquet apenas para chunk_strategy=hierarchical-child)

Cada combinação `(provider, model, chunk_strategy, metodo_extracao)` é um
pacote autocontido — Camada 3 baixa só o que precisa via `snapshot_download`
filtrando por `allow_patterns` neste prefixo.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import CommitOperationAdd, HfApi, snapshot_download

from src.config.settings import (
    HF_DATASET_REPO,
    VECTORSTORE_HUB_PREFIX,
    get_hf_token,
)
from src.vectorstore.faiss_store import (
    INDEX_FILENAME,
    FAISSVectorStore,
)
from src.vectorstore.manifest import (
    MANIFEST_FILENAME,
    load_manifest,
)
from src.vectorstore.metadata import (
    METADATA_FILENAME,
    PARENTS_FILENAME,
    load_metadata,
    load_parents,
)


def hub_prefix(
    *,
    provider: str,
    model: str,
    chunk_strategy: str,
    metodo_extracao: str,
) -> str:
    """Retorna o prefixo Hive-style usado tanto no upload quanto no download."""
    return (
        f"{VECTORSTORE_HUB_PREFIX}/"
        f"provider={provider}/"
        f"model={model}/"
        f"chunk_strategy={chunk_strategy}/"
        f"metodo_extracao={metodo_extracao}"
    )


def publicar_vectorstore(
    local_dir: str | Path,
    *,
    provider: str,
    model: str,
    chunk_strategy: str,
    metodo_extracao: str,
    repo_id: str | None = None,
) -> str:
    """Faz upload de `local_dir` (com index/metadata/manifest [/parents]).

    Apenas o sub-prefixo da combinação é tocado: `delete_patterns` garante que
    publicar uma vector store não apaga as outras 11 da matriz.
    """
    local_dir = Path(local_dir)
    if not (local_dir / INDEX_FILENAME).exists():
        raise FileNotFoundError(
            f"index.faiss ausente em {local_dir}. "
            "Construa a vector store antes de publicar."
        )
    if not (local_dir / METADATA_FILENAME).exists():
        raise FileNotFoundError(
            f"metadata.parquet ausente em {local_dir}."
        )
    if not (local_dir / MANIFEST_FILENAME).exists():
        raise FileNotFoundError(f"manifest.json ausente em {local_dir}.")
    if chunk_strategy == "hierarchical-child":
        if not (local_dir / PARENTS_FILENAME).exists():
            raise FileNotFoundError(
                f"parents.parquet ausente em {local_dir} "
                "(obrigatório para hierarchical-child)."
            )

    if repo_id is None:
        repo_id = HF_DATASET_REPO

    prefix = hub_prefix(
        provider=provider,
        model=model,
        chunk_strategy=chunk_strategy,
        metodo_extracao=metodo_extracao,
    )

    token = get_hf_token()
    api = HfApi(token=token)

    arquivos = [INDEX_FILENAME, METADATA_FILENAME, MANIFEST_FILENAME]
    if chunk_strategy == "hierarchical-child":
        arquivos.append(PARENTS_FILENAME)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commit_msg = (
        f"Vector store: provider={provider} model={model} "
        f"strategy={chunk_strategy} metodo={metodo_extracao} ({timestamp})"
    )

    print(f"  Fazendo upload de vector store para {repo_id}...")
    print(f"  Prefixo: {prefix}/")
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=commit_msg,
        operations=[
            CommitOperationAdd(
                path_in_repo=f"{prefix}/{nome}",
                path_or_fileobj=local_dir / nome,
            )
            for nome in arquivos
        ],
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  Upload concluido: {url}")
    return url


def publicar_vectorstore_memoria(
    *,
    store: FAISSVectorStore,
    metadata,
    manifest: dict[str, Any],
    parents=None,
    provider: str,
    model: str,
    chunk_strategy: str,
    metodo_extracao: str,
    repo_id: str | None = None,
) -> str:
    """Publica a vector store no Hub sem criar arquivos no filesystem local."""
    if chunk_strategy == "hierarchical-child" and parents is None:
        raise RuntimeError(
            "hierarchical-child exige parents.parquet para publicação."
        )
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    prefix = hub_prefix(
        provider=provider,
        model=model,
        chunk_strategy=chunk_strategy,
        metodo_extracao=metodo_extracao,
    )

    token = get_hf_token()
    api = HfApi(token=token)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commit_msg = (
        f"Vector store: provider={provider} model={model} "
        f"strategy={chunk_strategy} metodo={metodo_extracao} ({timestamp})"
    )

    operations = [
        CommitOperationAdd(
            path_in_repo=f"{prefix}/{INDEX_FILENAME}",
            path_or_fileobj=store.to_bytes(),
        ),
        CommitOperationAdd(
            path_in_repo=f"{prefix}/{METADATA_FILENAME}",
            path_or_fileobj=_dataframe_to_parquet_bytes(metadata),
        ),
        CommitOperationAdd(
            path_in_repo=f"{prefix}/{MANIFEST_FILENAME}",
            path_or_fileobj=json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8"),
        ),
    ]
    if parents is not None:
        operations.append(
            CommitOperationAdd(
                path_in_repo=f"{prefix}/{PARENTS_FILENAME}",
                path_or_fileobj=_dataframe_to_parquet_bytes(parents),
            )
        )

    print(f"  Fazendo upload em memória para {repo_id}...")
    print(f"  Prefixo: {prefix}/")
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=commit_msg,
        operations=operations,
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  Upload concluido: {url}")
    return url


def _dataframe_to_parquet_bytes(df) -> bytes:
    """Serializa DataFrame em Parquet na memória."""
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    return buffer.getvalue()


def carregar_vectorstore(
    *,
    provider: str,
    model: str,
    chunk_strategy: str,
    metodo_extracao: str,
    repo_id: str | None = None,
) -> dict[str, Any]:
    """Baixa a vector store do Hub e devolve `{index, metadata, parents, manifest, dir}`.

    `index` é uma `FAISSVectorStore` já carregada (pronta para `.search`).
    `parents` é `None` para estratégias diferentes de `hierarchical-child`.
    `dir` é o diretório local onde os arquivos foram materializados — útil
    se o consumidor quiser passar adiante.
    """
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    prefix = hub_prefix(
        provider=provider,
        model=model,
        chunk_strategy=chunk_strategy,
        metodo_extracao=metodo_extracao,
    )

    print(f"  Baixando vector store de {repo_id}: {prefix}/ ...")
    snapshot = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        allow_patterns=[f"{prefix}/*"],
    )
    local_dir = Path(snapshot) / prefix
    if not local_dir.exists():
        raise FileNotFoundError(
            f"Vector store não encontrada no Hub: {prefix}/. "
            "Verifique provider/model/chunk_strategy/metodo_extracao."
        )

    return {
        "index": FAISSVectorStore.load(local_dir),
        "metadata": load_metadata(local_dir),
        "parents": load_parents(local_dir),
        "manifest": load_manifest(local_dir),
        "dir": local_dir,
    }


def vectorstore_artifacts_present_hub(
    *,
    provider: str,
    model: str,
    chunk_strategy: str,
    metodo_extracao: str,
    repo_id: str | None = None,
) -> bool:
    """True se os arquivos da vector store já existem no HuggingFace Hub."""
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    prefix = hub_prefix(
        provider=provider,
        model=model,
        chunk_strategy=chunk_strategy,
        metodo_extracao=metodo_extracao,
    )
    required = {
        f"{prefix}/{INDEX_FILENAME}",
        f"{prefix}/{METADATA_FILENAME}",
        f"{prefix}/{MANIFEST_FILENAME}",
    }
    if chunk_strategy == "hierarchical-child":
        required.add(f"{prefix}/{PARENTS_FILENAME}")

    api = HfApi()
    arquivos = set(api.list_repo_files(repo_id, repo_type="dataset"))
    return required.issubset(arquivos)


def vectorstore_artifacts_present(directory: str | Path) -> bool:
    """True se index + metadata + manifest já existem em `directory`."""
    directory = Path(directory)
    return (
        (directory / INDEX_FILENAME).exists()
        and (directory / METADATA_FILENAME).exists()
        and (directory / MANIFEST_FILENAME).exists()
    )
