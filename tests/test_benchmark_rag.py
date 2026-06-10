"""Testes do benchmark RAG ponta-a-ponta sem rede e sem LLM real."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.evaluation.benchmark import (
    BenchmarkResult,
    StoreConfig,
    build_rag_failure_analysis,
    build_rag_baseline_configs,
    build_rag_rerank_pairing,
    evaluate_question_rag,
    load_benchmark_result_from_per_question_json,
    render_rag_rerank_pairing_md,
    run_rag_benchmark,
    run_rag_config,
)


class _FakeRAG:
    strategy = "fake"

    def __init__(self, contexts: list[dict[str, Any]], citations: list[str]):
        self._contexts = contexts
        self._citations = citations

    def query(self, pergunta: str, top_k: int = 10) -> dict[str, Any]:
        return {
            "answer": "Resposta gerada [1].",
            "citations": list(self._citations),
            "contexts": [dict(ctx) for ctx in self._contexts[:top_k]],
            "latency_ms": 12.0,
            "strategy": self.strategy,
            "generator_status": "ok",
            "generator_error": None,
        }


def _context(
    chunk_id: str,
    *,
    document_id: str,
    artigo: str | None = None,
    citation_label: str | None = None,
    texto: str = "trecho de apoio",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "artigo": artigo,
        "texto": texto,
        "citation_label": citation_label or chunk_id,
    }


def _question(question_id: str = "gt-0001") -> dict[str, Any]:
    return {
        "question_id": question_id,
        "question": "pergunta regulatoria",
        "reference_answer": "resposta de referencia",
        "relevant_sources": [
            {
                "document_id": "ren-2021-1000",
                "section_label": "Art. 1º",
                "support_excerpt": "trecho de apoio",
                "relevance": 3,
            }
        ],
    }


def _config(*, rerank: bool = False) -> StoreConfig:
    return StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        rerank=rerank,
    )


def _llm_metrics(**kwargs):
    return {
        "faithfulness": 0.8,
        "answer_correctness": 0.7,
        "llm_status": "ok",
    }


def _llm_metrics_usable(**kwargs):
    return {
        "faithfulness": 0.9,
        "answer_correctness": 0.9,
        "llm_status": "ok",
    }


def test_build_rag_baseline_configs_limita_escopo_a_baseline_e_rerank():
    configs = build_rag_baseline_configs()

    assert len(configs) == 2
    assert [config.rerank for config in configs] == [False, True]
    assert {config.model for config in configs} == {"text-embedding-3-large"}
    assert {config.chunk_strategy for config in configs} == {"fixed-size"}
    assert {config.metodo_extracao for config in configs} == {"markdown"}
    assert {config.mode for config in configs} == {"flat"}
    # Fase 2: pool 100 é o default do rerank (promovido pelo pareamento).
    assert configs[0].candidates_k_override is None
    assert configs[1].candidates_k_override == 100


def test_evaluate_question_rag_calcula_metricas_e_citation_accuracy():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        ),
        _context(
            "doc-b::0",
            document_id="outra-norma",
            artigo="Art. 9º",
            citation_label="Outro documento",
        ),
    ]
    rag = _FakeRAG(contexts, citations=["REN 1000/2021, Art. 1º"])

    result = evaluate_question_rag(
        rag,
        _question(),
        top_k=2,
        llm_metrics_fn=_llm_metrics,
    )

    assert result["question_id"] == "gt-0001"
    assert result["recall_at_k"] == 1.0
    assert result["doc_recall_at_k"] == 1.0
    assert result["citation_accuracy"] == 1.0
    assert result["faithfulness"] == 0.8
    assert result["answer_correctness"] == 0.7
    assert result["answer_usable"] is False
    assert result["failure_type"] == "answer_quality_failure"
    assert result["generator_status"] == "ok"


def test_evaluate_question_rag_marca_resposta_usavel_quando_metricas_passam():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        )
    ]
    rag = _FakeRAG(contexts, citations=["REN 1000/2021, Art. 1º"])

    result = evaluate_question_rag(
        rag,
        _question(),
        top_k=1,
        llm_metrics_fn=_llm_metrics_usable,
    )

    assert result["answer_usable"] is True
    assert result["failure_type"] == "usable"


def test_evaluate_question_rag_classifica_documento_errado_e_trecho_errado():
    doc_errado = _FakeRAG(
        [_context("doc-b::0", document_id="outra-norma", citation_label="Outra")],
        citations=["Outra"],
    )
    trecho_errado = _FakeRAG(
        [
            _context(
                "doc-a::0",
                document_id="ren-2021-1000",
                artigo="Art. 9º",
                citation_label="REN 1000/2021, Art. 9º",
                texto="conteudo de outro artigo",
            )
        ],
        citations=["REN 1000/2021, Art. 9º"],
    )

    result_doc = evaluate_question_rag(
        doc_errado,
        _question(),
        top_k=1,
        llm_metrics_fn=_llm_metrics_usable,
    )
    result_trecho = evaluate_question_rag(
        trecho_errado,
        _question(),
        top_k=1,
        llm_metrics_fn=_llm_metrics_usable,
    )

    assert result_doc["failure_type"] == "retrieval_document_failure"
    assert result_trecho["failure_type"] == "retrieval_passage_failure"


def test_evaluate_question_rag_zera_citation_accuracy_sem_citacoes():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        )
    ]
    rag = _FakeRAG(contexts, citations=[])

    result = evaluate_question_rag(
        rag,
        _question(),
        top_k=1,
        llm_metrics_fn=_llm_metrics,
    )

    assert result["citation_accuracy"] == 0.0


def test_run_rag_config_agrega_metricas_e_status_llm():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        )
    ]

    def rag_factory(config, repo_id, query_cache=None):
        return _FakeRAG(contexts, citations=["REN 1000/2021, Art. 1º"])

    result = run_rag_config(
        _config(),
        [_question("gt-0001"), _question("gt-0002")],
        top_k=1,
        rag_factory=rag_factory,
        llm_metrics_fn=_llm_metrics,
    )

    assert result["num_questions"] == 2
    assert result["faithfulness_avg"] == 0.8
    assert result["answer_correctness_avg"] == 0.7
    assert result["citation_accuracy_avg"] == 1.0
    assert result["answer_usable_rate"] == 0.0
    assert result["failure_type_counts"] == {"answer_quality_failure": 2}
    assert result["llm_status_counts"] == {"ok": 2}


def test_run_rag_benchmark_devolve_dataframe_e_pula_source_only():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        )
    ]

    def rag_factory(config, repo_id, query_cache=None):
        return _FakeRAG(contexts, citations=["REN 1000/2021, Art. 1º"])

    source_only = _question("gt-9999")
    source_only["answerability"] = "source_only"

    result = run_rag_benchmark(
        [_question("gt-0001"), source_only],
        top_k=1,
        configs=[_config()],
        rag_factory=rag_factory,
        llm_metrics_fn=_llm_metrics,
    )

    assert isinstance(result, BenchmarkResult)
    assert isinstance(result.metrics, pd.DataFrame)
    assert len(result.metrics) == 1
    row = result.metrics.iloc[0]
    assert row["num_questions_total"] == 2
    assert row["num_questions_evaluated"] == 1
    assert row["num_questions_skipped"] == 1
    assert result.skipped_questions[0]["question_id"] == "gt-9999"


def test_build_rag_failure_analysis_resume_falhas_por_config():
    rows = [
        {
            "model": "text-embedding-3-large",
            "chunk_strategy": "fixed-size",
            "metodo_extracao": "markdown",
            "mode": "flat",
            "rerank": False,
            "answer_usable_rate": 0.5,
            "failure_type_counts": {
                "usable": 1,
                "retrieval_document_failure": 1,
            },
            "per_question": [
                {
                    "question_id": "gt-0001",
                    "answer_usable": True,
                    "failure_type": "usable",
                    "recall_at_k": 1.0,
                    "doc_recall_at_k": 1.0,
                    "citation_accuracy": 1.0,
                    "answer_correctness": 0.9,
                },
                {
                    "question_id": "gt-0002",
                    "answer_usable": False,
                    "failure_type": "retrieval_document_failure",
                    "recall_at_k": 0.0,
                    "doc_recall_at_k": 0.0,
                    "citation_accuracy": 0.0,
                    "answer_correctness": 0.9,
                },
            ],
        }
    ]
    result = BenchmarkResult(
        metrics=pd.DataFrame(rows),
        skipped_questions=[],
        cache_stats={},
    )

    analysis = build_rag_failure_analysis(result)

    assert analysis["configs"][0]["label"] == (
        "text-embedding-3-large|fixed-size|markdown|flat"
    )
    assert analysis["configs"][0]["answer_usable_rate"] == 0.5
    assert analysis["configs"][0]["failure_type_counts"] == {
        "usable": 1,
        "retrieval_document_failure": 1,
    }
    assert analysis["configs"][0]["failures"][0]["question_id"] == "gt-0002"
    assert analysis["configs"][0]["failures"][0]["next_focus"] == (
        "query_expansion_or_retrieval"
    )


# -----------------------------------------------------------------------------
# Pareamento baseline vs baseline+rerank
# -----------------------------------------------------------------------------


def _pairing_question(
    question_id: str,
    *,
    answer_usable: bool,
    failure_type: str,
    recall_at_k: float = 0.0,
    doc_recall_at_k: float = 0.0,
) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "answer_usable": answer_usable,
        "failure_type": failure_type,
        "recall_at_k": recall_at_k,
        "doc_recall_at_k": doc_recall_at_k,
    }


def _count_failure_types(per_question: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for q in per_question:
        key = str(q.get("failure_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _pairing_result(
    *,
    baseline_per_question: list[dict[str, Any]],
    rerank_per_question: list[dict[str, Any]] | None,
) -> BenchmarkResult:
    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "model": "text-embedding-3-large",
            "chunk_strategy": "fixed-size",
            "metodo_extracao": "markdown",
            "mode": "flat",
            "rerank": False,
            "answer_usable_rate": (
                sum(1 for q in baseline_per_question if q["answer_usable"])
                / len(baseline_per_question)
            ),
            "failure_type_counts": _count_failure_types(baseline_per_question),
            "per_question": baseline_per_question,
        }
    )
    if rerank_per_question is not None:
        rows.append(
            {
                "model": "text-embedding-3-large",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "mode": "flat",
                "rerank": True,
                "answer_usable_rate": (
                    sum(1 for q in rerank_per_question if q["answer_usable"])
                    / len(rerank_per_question)
                ),
                "failure_type_counts": _count_failure_types(rerank_per_question),
                "per_question": rerank_per_question,
            }
        )
    return BenchmarkResult(
        metrics=pd.DataFrame(rows),
        skipped_questions=[],
        cache_stats={},
    )


def test_build_rag_rerank_pairing_classifica_buckets():
    baseline = [
        _pairing_question(
            "gt-0001", answer_usable=False, failure_type="retrieval_document_failure"
        ),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
        _pairing_question("gt-0003", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0004", answer_usable=False, failure_type="citation_failure"
        ),
        _pairing_question(
            "gt-0005", answer_usable=False, failure_type="answer_quality_failure"
        ),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0002", answer_usable=False, failure_type="retrieval_document_failure"
        ),
        _pairing_question("gt-0003", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0004", answer_usable=False, failure_type="citation_failure"
        ),
        _pairing_question(
            "gt-0005",
            answer_usable=False,
            failure_type="retrieval_passage_failure",
        ),
    ]
    pairing = build_rag_rerank_pairing(
        _pairing_result(
            baseline_per_question=baseline,
            rerank_per_question=rerank,
        )
    )

    def _ids(name: str) -> list[str]:
        return [q["question_id"] for q in pairing["buckets"][name]["questions"]]

    assert _ids("saved_by_rerank") == ["gt-0001"]
    assert _ids("broken_by_rerank") == ["gt-0002"]
    assert _ids("stable_pass") == ["gt-0003"]
    assert _ids("stable_fail_same_type") == ["gt-0004"]
    assert _ids("stable_fail_changed_type") == ["gt-0005"]
    assert pairing["summary"]["saved_count"] == 1
    assert pairing["summary"]["broken_count"] == 1
    assert pairing["summary"]["net_delta"] == 0
    # delta_doc_failure: baseline tem 1 retrieval_document_failure, rerank tem 1.
    assert pairing["summary"]["delta_doc_failure"] == 0


def test_build_rag_rerank_pairing_erra_sem_config_rerank():
    baseline = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
    ]
    result = _pairing_result(
        baseline_per_question=baseline,
        rerank_per_question=None,
    )

    with pytest.raises(ValueError, match="rerank pairing requer"):
        build_rag_rerank_pairing(result)


def test_build_rag_rerank_pairing_erra_question_id_assimetrico():
    baseline = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0003", answer_usable=False, failure_type="citation_failure"
        ),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0002", answer_usable=False, failure_type="citation_failure"
        ),
    ]
    result = _pairing_result(
        baseline_per_question=baseline,
        rerank_per_question=rerank,
    )

    with pytest.raises(ValueError, match="mesmo conjunto de question_id"):
        build_rag_rerank_pairing(result)


def test_build_rag_rerank_pairing_decision_promote():
    # 4 saved, 1 broken, delta_doc_failure baixo -> promote.
    # Baseline: 5 não-usáveis (4 doc_failure, 1 usable). Rerank: 4 saved, 1 broken.
    baseline = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
        _pairing_question(
            "gt-0002",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
        _pairing_question(
            "gt-0003",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
        _pairing_question(
            "gt-0004",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
        _pairing_question("gt-0005", answer_usable=True, failure_type="usable"),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
        _pairing_question("gt-0003", answer_usable=True, failure_type="usable"),
        _pairing_question("gt-0004", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0005",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
    ]
    pairing = build_rag_rerank_pairing(
        _pairing_result(
            baseline_per_question=baseline,
            rerank_per_question=rerank,
        )
    )

    assert pairing["decision_rule"]["verdict"] == "promote"
    assert pairing["decision_rule"]["reasons"] == []


def test_build_rag_rerank_pairing_decision_keep_optional_por_broken():
    baseline = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="citation_failure",
        ),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0002",
            answer_usable=False,
            failure_type="citation_failure",
        ),
    ]
    pairing = build_rag_rerank_pairing(
        _pairing_result(
            baseline_per_question=baseline,
            rerank_per_question=rerank,
        )
    )

    assert pairing["decision_rule"]["verdict"] == "keep_optional"
    assert any("saved" in r for r in pairing["decision_rule"]["reasons"])


def test_build_rag_rerank_pairing_decision_keep_optional_por_doc_failure():
    # 10 salvos vs 1 quebrado, mas delta_doc_failure=+2 -> keep_optional.
    baseline = []
    rerank = []
    for i in range(1, 11):
        qid = f"gt-{i:04d}"
        baseline.append(
            _pairing_question(
                qid,
                answer_usable=False,
                failure_type="citation_failure",
            )
        )
        rerank.append(_pairing_question(qid, answer_usable=True, failure_type="usable"))
    # 1 broken: baseline true -> rerank doc_failure
    baseline.append(
        _pairing_question("gt-0011", answer_usable=True, failure_type="usable")
    )
    rerank.append(
        _pairing_question(
            "gt-0011",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        )
    )
    # 2 perguntas que ficam doc_failure só no rerank, sem afetar saved/broken
    # (ambos não-usáveis com tipos diferentes).
    baseline.append(
        _pairing_question(
            "gt-0012",
            answer_usable=False,
            failure_type="answer_quality_failure",
        )
    )
    rerank.append(
        _pairing_question(
            "gt-0012",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        )
    )

    pairing = build_rag_rerank_pairing(
        _pairing_result(
            baseline_per_question=baseline,
            rerank_per_question=rerank,
        )
    )

    assert pairing["summary"]["saved_count"] == 10
    assert pairing["summary"]["broken_count"] == 1
    assert pairing["summary"]["delta_doc_failure"] == 2
    assert pairing["decision_rule"]["verdict"] == "keep_optional"
    assert any(
        "delta_doc_failure" in reason
        for reason in pairing["decision_rule"]["reasons"]
    )


def test_render_rag_rerank_pairing_md_inclui_veredito():
    baseline = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="retrieval_document_failure",
        ),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
    ]
    pairing = build_rag_rerank_pairing(
        _pairing_result(
            baseline_per_question=baseline,
            rerank_per_question=rerank,
        )
    )

    markdown = render_rag_rerank_pairing_md(pairing)
    assert "# Pareamento rerank vs baseline" in markdown
    assert "## Veredito" in markdown
    assert "**promote**" in markdown
    assert "gt-0001" in markdown


def test_build_rag_rerank_pairing_idempotente():
    baseline = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="citation_failure",
        ),
        _pairing_question("gt-0002", answer_usable=True, failure_type="usable"),
    ]
    rerank = [
        _pairing_question("gt-0001", answer_usable=True, failure_type="usable"),
        _pairing_question(
            "gt-0002",
            answer_usable=False,
            failure_type="citation_failure",
        ),
    ]
    result = _pairing_result(
        baseline_per_question=baseline,
        rerank_per_question=rerank,
    )
    first = build_rag_rerank_pairing(result)
    second = build_rag_rerank_pairing(result)
    assert first == second


def test_load_benchmark_result_from_per_question_json_reconstroi_metrics(
    tmp_path: Path,
) -> None:
    payload = {
        "generated_at": "2026-01-01T00:00:00Z",
        "top_k": 10,
        "skipped_questions": [],
        "cache_stats": {},
        "results": [
            {
                "model": "text-embedding-3-large",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "mode": "flat",
                "rerank": False,
                "per_question": [
                    _pairing_question(
                        "gt-0001", answer_usable=True, failure_type="usable"
                    ),
                    _pairing_question(
                        "gt-0002",
                        answer_usable=False,
                        failure_type="retrieval_document_failure",
                    ),
                ],
            },
            {
                "model": "text-embedding-3-large",
                "chunk_strategy": "fixed-size",
                "metodo_extracao": "markdown",
                "mode": "flat",
                "rerank": True,
                "per_question": [
                    _pairing_question(
                        "gt-0001", answer_usable=True, failure_type="usable"
                    ),
                    _pairing_question(
                        "gt-0002", answer_usable=True, failure_type="usable"
                    ),
                ],
            },
        ],
    }
    path = tmp_path / "per_question.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = load_benchmark_result_from_per_question_json(path)

    assert len(result.metrics) == 2
    baseline_row = result.metrics[result.metrics["rerank"] == False].iloc[0]  # noqa: E712
    assert baseline_row["answer_usable_rate"] == 0.5
    assert baseline_row["failure_type_counts"] == {
        "usable": 1,
        "retrieval_document_failure": 1,
    }

    # Permite passar direto para análises sem rerodar LLM.
    pairing = build_rag_rerank_pairing(result)
    assert pairing["summary"]["saved_count"] == 1
    assert pairing["summary"]["broken_count"] == 0


# -----------------------------------------------------------------------------
# Fase 2 — rerank pool comparison
# -----------------------------------------------------------------------------


def test_build_rag_baseline_configs_rerank_pools_gera_tres_configs():
    configs = build_rag_baseline_configs(rerank_pools=(50, 100))

    assert len(configs) == 3
    assert [c.rerank for c in configs] == [False, True, True]
    assert [c.candidates_k_override for c in configs] == [None, 50, 100]
    # labels distinguem os pools para serialização/inspeção
    labels = [c.label for c in configs]
    assert any(label.endswith("+rerank@pool50") for label in labels)
    assert any(label.endswith("+rerank@pool100") for label in labels)


def test_build_rag_baseline_configs_rerank_pools_incompativel_com_qe():
    with pytest.raises(ValueError, match="mutuamente exclusiv"):
        build_rag_baseline_configs(query_expansion=True, rerank_pools=(50, 100))


def test_run_rag_config_emite_candidates_k():
    contexts = [
        _context(
            "doc-a::0",
            document_id="ren-2021-1000",
            artigo="Art. 1º",
            citation_label="REN 1000/2021, Art. 1º",
        )
    ]

    def rag_factory(config, repo_id, query_cache=None):
        return _FakeRAG(contexts, citations=["REN 1000/2021, Art. 1º"])

    config = StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
        rerank=True,
        candidates_k_override=100,
    )
    result = run_rag_config(
        config,
        [_question("gt-0001")],
        top_k=1,
        rag_factory=rag_factory,
        llm_metrics_fn=_llm_metrics,
    )

    assert result["candidates_k"] == 100


def _pool_config(
    per_question: list[dict[str, Any]],
    *,
    rerank: bool,
    candidates_k: int | None,
) -> dict[str, Any]:
    return {
        "rerank": rerank,
        "candidates_k": candidates_k,
        "per_question": per_question,
    }


def test_build_pool_pairing_promote():
    from scripts.analyze_rerank_pool_pairing import build_pool_pairing

    # pool50: 2 falhas; pool100 salva as 2, quebra 0; doc_recall não cai.
    pool50 = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="retrieval_document_failure",
            doc_recall_at_k=0.0,
        ),
        _pairing_question(
            "gt-0002",
            answer_usable=False,
            failure_type="retrieval_document_failure",
            doc_recall_at_k=0.0,
        ),
        _pairing_question(
            "gt-0003", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
    ]
    pool100 = [
        _pairing_question(
            "gt-0001", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
        _pairing_question(
            "gt-0002", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
        _pairing_question(
            "gt-0003", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
    ]
    pairing = build_pool_pairing(
        _pool_config(pool50, rerank=True, candidates_k=50),
        _pool_config(pool100, rerank=True, candidates_k=100),
    )

    assert pairing["summary"]["saved_count"] == 2
    assert pairing["summary"]["broken_count"] == 0
    assert pairing["decision_rule"]["verdict"] == "promote"
    assert pairing["decision_rule"]["reasons"] == []


def test_build_pool_pairing_keep_pool50_por_broken():
    from scripts.analyze_rerank_pool_pairing import build_pool_pairing

    # 1 saved, 1 broken -> saved < 2*broken -> keep_pool50.
    pool50 = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="citation_failure",
            doc_recall_at_k=1.0,
        ),
        _pairing_question(
            "gt-0002", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
    ]
    pool100 = [
        _pairing_question(
            "gt-0001", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
        _pairing_question(
            "gt-0002",
            answer_usable=False,
            failure_type="citation_failure",
            doc_recall_at_k=1.0,
        ),
    ]
    pairing = build_pool_pairing(
        _pool_config(pool50, rerank=True, candidates_k=50),
        _pool_config(pool100, rerank=True, candidates_k=100),
    )

    assert pairing["summary"]["saved_count"] == 1
    assert pairing["summary"]["broken_count"] == 1
    assert pairing["decision_rule"]["verdict"] == "keep_pool50"
    assert any("saved=1 < 2*broken=2" in r for r in pairing["decision_rule"]["reasons"])


def test_build_pool_pairing_keep_pool50_por_doc_recall():
    from scripts.analyze_rerank_pool_pairing import build_pool_pairing

    # saved>=2*broken, mas doc_recall cai além de -0.02 -> keep_pool50.
    pool50 = [
        _pairing_question(
            "gt-0001",
            answer_usable=False,
            failure_type="retrieval_passage_failure",
            doc_recall_at_k=1.0,
        ),
        _pairing_question(
            "gt-0002", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
    ]
    pool100 = [
        _pairing_question(
            "gt-0001", answer_usable=True, failure_type="usable", doc_recall_at_k=0.0
        ),
        _pairing_question(
            "gt-0002", answer_usable=True, failure_type="usable", doc_recall_at_k=0.0
        ),
    ]
    pairing = build_pool_pairing(
        _pool_config(pool50, rerank=True, candidates_k=50),
        _pool_config(pool100, rerank=True, candidates_k=100),
    )

    assert pairing["summary"]["saved_count"] == 1
    assert pairing["summary"]["broken_count"] == 0
    assert pairing["summary"]["delta_doc_recall"] == pytest.approx(-1.0)
    assert pairing["decision_rule"]["verdict"] == "keep_pool50"
    assert any("delta_doc_recall" in r for r in pairing["decision_rule"]["reasons"])


def test_render_pool_pairing_md_inclui_veredito():
    from scripts.analyze_rerank_pool_pairing import (
        build_pool_pairing,
        render_pool_pairing_md,
    )

    cfg = [
        _pairing_question(
            "gt-0001", answer_usable=True, failure_type="usable", doc_recall_at_k=1.0
        ),
    ]
    par = build_pool_pairing(
        _pool_config(cfg, rerank=True, candidates_k=50),
        _pool_config(cfg, rerank=True, candidates_k=100),
    )
    md = render_pool_pairing_md(par, par)

    assert "Par 1 — DECISÃO" in md
    assert "veredito" in md
    assert "delta_doc_recall" in md
