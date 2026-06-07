"""Testes do benchmark RAG ponta-a-ponta sem rede e sem LLM real."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.evaluation.benchmark import (
    BenchmarkResult,
    StoreConfig,
    build_rag_baseline_configs,
    evaluate_question_rag,
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
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "artigo": artigo,
        "texto": "trecho de apoio",
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


def test_build_rag_baseline_configs_limita_escopo_a_baseline_e_rerank():
    configs = build_rag_baseline_configs()

    assert len(configs) == 2
    assert [config.rerank for config in configs] == [False, True]
    assert {config.model for config in configs} == {"text-embedding-3-large"}
    assert {config.chunk_strategy for config in configs} == {"fixed-size"}
    assert {config.metodo_extracao for config in configs} == {"markdown"}
    assert {config.mode for config in configs} == {"flat"}


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
    assert result["generator_status"] == "ok"


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
