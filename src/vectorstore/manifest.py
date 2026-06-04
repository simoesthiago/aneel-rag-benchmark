"""Manifesto de uma vector store FAISS publicada na Camada 2.3.

O manifest é a prova auditável de como o índice foi construído. Sem ele, dois
índices com o mesmo nome de arquivo podem ter sido gerados com modelos ou
estratégias diferentes — o que invalida qualquer comparação de benchmark.

O manifest viaja sempre junto do `index.faiss` e do `metadata.parquet`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MANIFEST_FILENAME = "manifest.json"


def build_manifest(
    *,
    provider: str,
    model: str,
    dimension: int,
    chunk_strategy: str,
    metodo_extracao: str,
    count: int,
    chunk_ids: Iterable[str],
    corpus_repo: str,
    normalized: bool = True,
    metric: str = "ip",
    index_type: str = "IndexFlatIP",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta o dicionário do manifest a partir dos parâmetros de execução.

    `chunk_ids` é consumido apenas para gerar um hash curto que permite
    auditar reprodutibilidade sem armazenar todos os IDs no manifest.
    """
    chunk_ids_list = list(chunk_ids)
    if count != len(chunk_ids_list):
        raise ValueError(
            f"count={count} divergente de len(chunk_ids)={len(chunk_ids_list)}"
        )

    manifest: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "dimension": int(dimension),
        "chunk_strategy": chunk_strategy,
        "metodo_extracao": metodo_extracao,
        "count": int(count),
        "normalized": bool(normalized),
        "metric": metric,
        "index_type": index_type,
        "corpus_repo": corpus_repo,
        "chunk_ids_hash": hash_chunk_ids(chunk_ids_list),
        "created_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    if extra:
        manifest["extra"] = extra
    return manifest


def save_manifest(directory: str | Path, manifest: dict[str, Any]) -> Path:
    """Serializa o manifest em `directory/manifest.json`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST_FILENAME
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def load_manifest(directory: str | Path) -> dict[str, Any]:
    """Carrega o manifest de `directory/manifest.json`."""
    path = Path(directory) / MANIFEST_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"manifest.json não encontrado em {directory}. "
            "A vector store está incompleta."
        )
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def hash_chunk_ids(chunk_ids: Iterable[str]) -> str:
    """Hash curto e estável da lista de chunk_ids para auditoria."""
    digest = hashlib.sha256()
    for chunk_id in chunk_ids:
        digest.update(str(chunk_id).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]
