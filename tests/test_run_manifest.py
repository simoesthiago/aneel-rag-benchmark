"""Testes do manifesto padrão de runs de benchmark (Marco A).

Cobrem o contrato do `manifest.json`: formato do run_id, diretório default por
modo, e os campos obrigatórios do manifesto montado a partir de um DataFrame
agregado real. Tudo offline (sem rede, sem LLM).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pandas as pd

from src.evaluation.run_manifest import (
    MANIFEST_SCHEMA_VERSION,
    build_run_manifest,
    default_run_dir,
    make_run_id,
    write_run_manifest,
)


def _fake_aggregate() -> pd.DataFrame:
    """Agregado mínimo no formato do benchmark (config + métrica)."""
    return pd.DataFrame(
        [
            {
                "model": "text-embedding-3-large",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "mode": "flat",
                "rerank": False,
                "candidates_k": None,
                "exclude_revogadas": False,
                "doc_recall_at_k": 0.875,
            },
            {
                "model": "text-embedding-3-large",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "mode": "flat",
                "rerank": True,
                "candidates_k": 100,
                "exclude_revogadas": True,
                "doc_recall_at_k": 0.979,
            },
        ]
    )


def test_make_run_id_formato_ordenavel() -> None:
    fixed = datetime(2026, 6, 12, 14, 30, 0, tzinfo=timezone.utc)
    run_id = make_run_id(now=fixed)
    # Prefixo de timestamp UTC fixo + sufixo de proveniência.
    assert run_id.startswith("20260612T143000Z-")
    assert re.fullmatch(r"20260612T143000Z-[\w.-]+", run_id)


def test_default_run_dir_por_modo() -> None:
    assert default_run_dir("rag", run_id="abc").as_posix() == (
        "data/evaluation/runs/rag/abc"
    )
    assert default_run_dir("retrieval", run_id="abc").as_posix() == (
        "data/evaluation/runs/retrieval/abc"
    )


def test_default_run_dir_modo_invalido() -> None:
    import pytest

    with pytest.raises(ValueError):
        default_run_dir("invalido", run_id="x")


def test_build_run_manifest_campos_obrigatorios() -> None:
    manifest = build_run_manifest(
        mode="rag",
        run_id="20260612T143000Z-deadbee",
        aggregate=_fake_aggregate(),
        top_k=10,
        ground_truth_version="retrieval-50-v2",
        ground_truth_source="hub",
        num_questions=50,
        num_skipped=2,
        cache_stats={"hits": 3, "misses": 1},
        models={"embedding_model": "text-embedding-3-large", "llm_model": "gpt"},
        artifact_paths={"results_csv": "results.csv"},
    )
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["mode"] == "rag"
    assert manifest["run_id"] == "20260612T143000Z-deadbee"
    assert manifest["top_k"] == 10
    assert manifest["ground_truth"] == {
        "version": "retrieval-50-v2",
        "source": "hub",
        "num_questions": 50,
        "num_skipped": 2,
        "num_evaluable": 48,
    }
    # Cada config do agregado vira uma entrada com flags + métricas reais.
    assert len(manifest["configs"]) == 2
    assert manifest["configs"][1]["doc_recall_at_k"] == 0.979
    assert manifest["configs"][1]["candidates_k"] == 100
    # NaN/None do pandas viram null serializável.
    assert manifest["configs"][0]["candidates_k"] is None
    assert manifest["cache_stats"] == {"hits": 3, "misses": 1}
    # O manifesto inteiro precisa ser serializável em JSON.
    json.dumps(manifest)


def test_write_run_manifest_grava_arquivo(tmp_path) -> None:
    manifest = build_run_manifest(
        mode="retrieval",
        run_id="r1",
        aggregate=_fake_aggregate(),
        top_k=10,
        ground_truth_version="retrieval-50-v2",
        ground_truth_source="hub",
        num_questions=50,
        num_skipped=2,
        cache_stats=None,
        models={"embedding_model": "text-embedding-3-large"},
        artifact_paths={"results_csv": "results.csv"},
    )
    out = tmp_path / "run"
    path = write_run_manifest(out, manifest)
    assert path == out / "manifest.json"
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["run_id"] == "r1"
    assert reloaded["mode"] == "retrieval"
