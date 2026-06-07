"""Testes do loop de benchmark da Camada 3."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.evaluation.benchmark import (
    BenchmarkResult,
    StoreConfig,
    build_store_configs,
    evaluate_question,
    run_config,
    run_full_benchmark,
)


class _FakeRetriever:
    """Devolve sempre os mesmos chunks pré-definidos."""

    def __init__(self, chunks: list[dict[str, Any]]):
        self._chunks = chunks

    def retrieve(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        return [dict(chunk) for chunk in self._chunks[:top_k]]


def _question(question_id: str = "gt-0001") -> dict[str, Any]:
    return {
        "question_id": question_id,
        "question": "pergunta de teste",
        "relevant_sources": [
            {
                "document_id": "ren-2021-1000",
                "section_label": "Art. 1º, §1º",
                "support_excerpt": "trecho de apoio",
                "relevance": 3,
            }
        ],
    }


def _source_only_question(question_id: str = "gt-9999") -> dict[str, Any]:
    question = _question(question_id)
    question["answerability"] = "source_only"
    return question


def test_build_store_configs_gera_16_configuracoes_unicas():
    configs = build_store_configs()
    assert len(configs) == 16
    assert len(set(c.label for c in configs)) == 16
    assert (
        sum(1 for c in configs if c.chunk_strategy == "hierarchical-child")
        == 8
    )
    assert sum(1 for c in configs if c.mode == "hierarchical") == 4


def test_build_store_configs_com_rerank_duplica_matriz():
    configs = build_store_configs(include_rerank=True)
    assert len(configs) == 32
    assert sum(1 for c in configs if c.rerank) == 16
    assert sum(1 for c in configs if not c.rerank) == 16
    assert len({c.label for c in configs}) == 32


def test_build_store_configs_aplica_pool_apenas_no_rerank():
    configs = build_store_configs(
        include_rerank=True,
        rerank_candidates_k=100,
    )

    rerank_configs = [c for c in configs if c.rerank]
    baseline_configs = [c for c in configs if not c.rerank]

    assert {c.candidates_k_override for c in rerank_configs} == {100}
    assert {c.candidates_k_override for c in baseline_configs} == {None}
    assert all("+rerank@pool100" in c.label for c in rerank_configs)


def test_evaluate_question_calcula_metricas_de_retrieval():
    chunks = [
        {
            "chunk_id": "doc-a::0",
            "document_id": "ren-2021-1000",
            "artigo": "Art. 1º",
            "paragrafo": "§1º",
            "texto": "trecho relevante",
        },
        {
            "chunk_id": "doc-a::1",
            "document_id": "outra-norma",
            "artigo": "Art. 5º",
            "texto": "irrelevante",
        },
    ]
    retriever = _FakeRetriever(chunks)
    resultado = evaluate_question(retriever, _question(), top_k=2)

    assert resultado["recall_at_k"] == 1.0
    assert resultado["doc_recall_at_k"] == 1.0
    assert resultado["precision_at_k"] == 0.5
    assert resultado["mrr_at_k"] == 1.0
    assert resultado["ndcg_at_k"] == 1.0
    assert resultado["num_relevant_retrieved"] == 1
    assert resultado["num_expected_sources"] == 1
    assert resultado["latency_ms"] >= 0


def test_evaluate_question_sem_acertos_zera_recall_e_mrr():
    chunks = [
        {
            "chunk_id": "x::0",
            "document_id": "outra-norma",
            "artigo": "Art. 9º",
            "texto": "nada a ver",
        }
    ]
    retriever = _FakeRetriever(chunks)
    resultado = evaluate_question(retriever, _question(), top_k=1)

    assert resultado["recall_at_k"] == 0.0
    assert resultado["mrr_at_k"] == 0.0
    assert resultado["ndcg_at_k"] == 0.0


def test_run_config_agrega_por_config_com_metricas_medias():
    chunks = [
        {
            "chunk_id": "doc-a::0",
            "document_id": "ren-2021-1000",
            "artigo": "Art. 1º",
            "paragrafo": "§1º",
            "texto": "trecho",
        }
    ]

    def factory(config: StoreConfig, repo_id, query_cache=None):
        return _FakeRetriever(chunks)

    config = StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        mode="flat",
    )
    perguntas = [_question("gt-0001"), _question("gt-0002")]
    resultado = run_config(
        config, perguntas, top_k=1, retriever_factory=factory
    )

    assert resultado["num_questions"] == 2
    assert resultado["recall_at_k"] == 1.0
    assert resultado["ndcg_at_k"] == 1.0
    assert len(resultado["per_question"]) == 2
    assert resultado["latency_avg_ms"] is not None


def test_run_full_benchmark_paraleliza_com_max_workers():
    """ThreadPool deve produzir os mesmos resultados sequenciais."""
    chunks = [
        {
            "chunk_id": "doc-a::0",
            "document_id": "ren-2021-1000",
            "artigo": "Art. 1º",
            "paragrafo": "§1º",
            "texto": "trecho",
        }
    ]

    def factory(config, repo_id, query_cache=None):
        return _FakeRetriever(chunks)

    configs = [
        StoreConfig(
            provider="openai",
            model="text-embedding-3-large",
            chunk_strategy="article-aware",
            metodo_extracao=metodo,
            mode="flat",
        )
        for metodo in ("markdown", "texto")
    ]
    perguntas = [_question(f"gt-{i:04d}") for i in range(1, 4)]

    sequencial = run_full_benchmark(
        perguntas,
        top_k=1,
        configs=configs,
        retriever_factory=factory,
        max_workers=1,
    ).metrics
    paralelo = run_full_benchmark(
        perguntas,
        top_k=1,
        configs=configs,
        retriever_factory=factory,
        max_workers=4,
    ).metrics

    assert len(sequencial) == len(paralelo) == 2
    assert set(sequencial["metodo_extracao"]) == set(
        paralelo["metodo_extracao"]
    )
    assert sequencial["ndcg_at_k"].tolist() == paralelo["ndcg_at_k"].tolist()


def test_run_full_benchmark_devolve_dataframe_com_colunas_esperadas():
    chunks = [
        {
            "chunk_id": "doc-a::0",
            "document_id": "ren-2021-1000",
            "artigo": "Art. 1º",
            "paragrafo": "§1º",
            "texto": "trecho",
        }
    ]

    def factory(config, repo_id, query_cache=None):
        return _FakeRetriever(chunks)

    config = StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        mode="flat",
    )
    df = run_full_benchmark(
        [_question()],
        top_k=1,
        configs=[config],
        retriever_factory=factory,
    )

    assert isinstance(df, BenchmarkResult)
    assert isinstance(df.metrics, pd.DataFrame)
    assert df.skipped_questions == []
    df = df.metrics
    assert len(df) == 1
    assert {
        "model",
        "chunk_strategy",
        "metodo_extracao",
        "mode",
        "num_questions_total",
        "num_questions_evaluated",
        "num_questions_skipped",
        "recall_at_k",
        "precision_at_k",
        "mrr_at_k",
        "ndcg_at_k",
        "latency_avg_ms",
        "latency_p95_ms",
    }.issubset(df.columns)


def test_run_full_benchmark_pula_source_only_do_agregado():
    chunks = [
        {
            "chunk_id": "doc-a::0",
            "document_id": "ren-2021-1000",
            "artigo": "Art. 1º",
            "paragrafo": "§1º",
            "texto": "trecho",
        }
    ]

    def factory(config, repo_id, query_cache=None):
        return _FakeRetriever(chunks)

    config = StoreConfig(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="article-aware",
        metodo_extracao="markdown",
        mode="flat",
    )
    df = run_full_benchmark(
        [_question("gt-0001"), _source_only_question("gt-0002")],
        top_k=1,
        configs=[config],
        retriever_factory=factory,
    )

    assert isinstance(df, BenchmarkResult)
    assert df.skipped_questions == [
        {
            "question_id": "gt-0002",
            "answerability": "source_only",
            "reason": "answerability_not_evaluated",
        }
    ]

    row = df.metrics.iloc[0]
    assert row["num_questions_total"] == 2
    assert row["num_questions_evaluated"] == 1
    assert row["num_questions_skipped"] == 1
    assert row["num_questions"] == 1
