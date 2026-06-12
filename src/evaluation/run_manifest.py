"""Manifesto padrão para runs de benchmark (Marco A do contrato de `data/`).

Cada run de benchmark (retrieval ou RAG) passa a viver em
`data/evaluation/runs/<mode>/<run_id>/` com um `manifest.json` ao lado dos
artefatos (`results.csv`, `per_question.json`, etc.). O manifesto é o registro
auto-suficiente que torna o run auditável depois: quem rodou, contra qual
ground truth, em qual commit, com quais modelos/filtros e com que métricas.

Por que isto importa: sem manifesto, um `results.csv` solto não diz qual GT,
qual commit nem quais filtros de higiene geraram aquele número. O manifesto
fecha esse contrato antes de gastar OpenAI/Cohere nas matrizes grandes.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

# Schema do manifesto. Versionado para que um leitor futuro saiba interpretar o
# arquivo mesmo que campos sejam adicionados depois.
MANIFEST_SCHEMA_VERSION = 1

# Raiz do layout de runs. Mantida aqui (e não em settings) porque é um contrato
# de organização de `data/`, não uma configuração de execução.
RUNS_ROOT = Path("data/evaluation/runs")


def make_run_id(now: datetime | None = None) -> str:
    """Gera um run_id ordenável e único: `<timestamp>-<commit_curto>`.

    O prefixo de timestamp UTC garante ordenação cronológica natural
    (`ls runs/rag/ | tail -1` é o mais recente). O sufixo de commit amarra o
    run ao código que o produziu. Sufixo `-dirty` quando há mudanças não
    commitadas — sinaliza que o run não é 100% reprodutível a partir do Git.
    """
    moment = now or datetime.now(timezone.utc)
    timestamp = moment.strftime("%Y%m%dT%H%M%SZ")
    commit, dirty = _git_state()
    suffix = commit if commit else "nogit"
    if dirty:
        suffix += "-dirty"
    return f"{timestamp}-{suffix}"


def default_run_dir(mode: str, run_id: str | None = None) -> Path:
    """Diretório default de um run: `data/evaluation/runs/<mode>/<run_id>/`."""
    if mode not in ("rag", "retrieval"):
        raise ValueError(f"mode inválido para run dir: {mode!r}")
    return RUNS_ROOT / mode / (run_id or make_run_id())


def _git_state() -> tuple[str | None, bool]:
    """Retorna `(commit_curto, dirty)` do repositório atual.

    Falha silenciosa (retorna `(None, False)`) se git não estiver disponível —
    o manifesto continua sendo gerado, apenas sem proveniência de commit.
    """
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None, False
    try:
        # `--untracked-files=no`: dirty significa "código RASTREADO difere do
        # HEAD". Arquivos não rastreados não contam — senão o próprio diretório
        # de saída do run (criado antes de escrever o manifesto) auto-marcaria
        # todo run como dirty.
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            stderr=subprocess.DEVNULL,
        ).decode()
    except (subprocess.SubprocessError, FileNotFoundError):
        status = ""
    return commit, bool(status.strip())


def _aggregate_records(aggregate: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte o DataFrame agregado em registros JSON-safe.

    Usa o serializador do pandas para tratar `NaN -> null` e tipos numpy sem
    fabricar nada: cada registro é exatamente uma linha do agregado (config +
    métricas) já calculada pelo benchmark.
    """
    return json.loads(aggregate.to_json(orient="records"))


def build_run_manifest(
    *,
    mode: str,
    run_id: str,
    aggregate: pd.DataFrame,
    top_k: int,
    ground_truth_version: str,
    ground_truth_source: str,
    num_questions: int,
    num_skipped: int,
    cache_stats: dict[str, int] | None,
    models: dict[str, str],
    artifact_paths: dict[str, str],
    config_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Monta o dict do manifesto a partir de dados reais do run.

    `aggregate` é o DataFrame de métricas (sem a coluna `per_question`); cada
    config vira uma entrada com seus filtros/flags e métricas agregadas.

    `config_flags` (opcional) é a lista de flags por configuração, na mesma
    ordem das linhas do agregado — tipicamente `asdict(StoreConfig)`. Necessária
    porque o agregado do modo retrieval não materializa colunas como
    `exclude_revogadas`/`exclude_superseded_versions`; sem isso o manifesto
    não registraria os filtros de higiene do run. Mesclada por posição: os
    flags da config (definição autoritativa) prevalecem em colisão de chave;
    as colunas de métrica do agregado são preservadas.
    """
    commit, dirty = _git_state()
    configs = _aggregate_records(aggregate)
    if config_flags is not None:
        if len(config_flags) != len(configs):
            raise ValueError(
                "config_flags e linhas do agregado têm tamanhos diferentes "
                f"({len(config_flags)} vs {len(configs)}); não dá para parear "
                "por posição com segurança."
            )
        configs = [
            {**metrics, **flags}
            for flags, metrics in zip(config_flags, configs)
        ]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": commit,
        "git_dirty": dirty,
        "top_k": top_k,
        "ground_truth": {
            "version": ground_truth_version,
            "source": ground_truth_source,
            "num_questions": num_questions,
            "num_skipped": num_skipped,
            "num_evaluable": num_questions - num_skipped,
        },
        "models": models,
        "configs": configs,
        "cache_stats": dict(cache_stats or {}),
        "artifact_paths": artifact_paths,
    }


def write_run_manifest(output_dir: Path, manifest: dict[str, Any]) -> Path:
    """Grava `manifest.json` no diretório do run e retorna o caminho."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
