"""Runner de benchmark da Camada 3 (Retrieval) sobre as 12 vector stores.

O `run_full_benchmark` itera por todas as combinações relevantes da matriz
de stores publicadas e produz uma única tabela com as métricas por
configuração. Esse DataFrame é o deliverable central do benchmark.

Para retrieval, as estratégias avaliadas são:

- `mode=flat` em stores `fixed-size` e `article-aware` (8 medições).
- `mode=flat` em stores `hierarchical-child` (4 medições — devolve o filho
  diretamente, como controle do efeito hierárquico).
- `mode=hierarchical` em stores `hierarchical-child` (4 medições — busca no
  filho e devolve o pai).

Total: 16 medições. Cada uma roda as 50 perguntas do `retrieval-50`.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Iterable

import pandas as pd

from src.embeddings.cache import QueryEmbeddingCache
from src.evaluation.matching import (
    build_relevance_vector,
    document_groups,
    source_coverage,
)
from src.evaluation.metrics import (
    doc_recall_at_k,
    evaluate_response,
    latency_summary,
    ndcg_at_k,
    optional_llm_metrics,
)
from src.rag.generator import generate_llm_answer
from src.rag.naive import NaiveRAG
from src.rag.query_expander import QueryExpander
from src.rag.retriever import Retriever, RetrieverMode

PROVIDER = "openai"
EMBEDDING_MODELS = ("text-embedding-3-large", "text-embedding-3-small")
METODOS_EXTRACAO = ("markdown", "texto")
NON_HIERARCHICAL_STRATEGIES = ("fixed-size", "article-aware")
HIERARCHICAL_STRATEGY = "hierarchical-child"
EVALUATED_ANSWERABILITIES = frozenset({"corpus_supported"})
ANSWER_USABLE_MIN_CITATION_ACCURACY = 0.5
ANSWER_USABLE_MIN_ANSWER_CORRECTNESS = 0.8


@dataclass(frozen=True)
class StoreConfig:
    """Identifica uma configuração avaliável do benchmark.

    `candidates_k_override` é opcional e só faz sentido quando `rerank=True`:
    o Retriever pega `candidates_k_override` candidatos densos antes de
    reordenar via reranker. Sem rerank, usa `top_k` direto. Default None =
    comportamento padrão do Retriever (~50 com rerank ativo).
    """

    provider: str
    model: str
    chunk_strategy: str
    metodo_extracao: str
    mode: RetrieverMode
    rerank: bool = False
    candidates_k_override: int | None = None
    query_expansion: bool = False
    exclude_revogadas: bool = False

    @property
    def label(self) -> str:
        suffix = "+rerank" if self.rerank else ""
        if self.rerank and self.candidates_k_override:
            suffix += f"@pool{self.candidates_k_override}"
        if self.query_expansion:
            suffix += "+qe"
        if self.exclude_revogadas:
            suffix += "+sem_revogadas"
        return (
            f"{self.model}|{self.chunk_strategy}|{self.metodo_extracao}|"
            f"{self.mode}{suffix}"
        )


@dataclass(frozen=True)
class BenchmarkResult:
    """Resultado completo do benchmark sem metadados em DataFrame."""

    metrics: pd.DataFrame
    skipped_questions: list[dict[str, Any]]
    cache_stats: dict[str, int]


def build_store_configs(
    *,
    include_rerank: bool = False,
    rerank_candidates_k: int | None = None,
) -> list[StoreConfig]:
    """Gera as configurações da matriz de retrieval.

    - 16 configs base (Dense FAISS + Hierarchical, sem rerank).
    - Se `include_rerank=True`, duplica cada config com `rerank=True` → 32.
    - Se `rerank_candidates_k` for fornecido (ex: 100), aplica nas variantes
      rerank. Diagnóstico em 1.3-alt-b/Opção A mostrou que pool 50 (default
      do Retriever) deixa trechos profundos fora do alcance; pool 100 sobe
      passage_recall +4 pp ao custo de doc_recall -2 pp.
    """
    configs: list[StoreConfig] = []
    for model in EMBEDDING_MODELS:
        for metodo in METODOS_EXTRACAO:
            for strategy in NON_HIERARCHICAL_STRATEGIES:
                configs.append(
                    StoreConfig(
                        provider=PROVIDER,
                        model=model,
                        chunk_strategy=strategy,
                        metodo_extracao=metodo,
                        mode="flat",
                    )
                )
            for mode in ("flat", "hierarchical"):
                configs.append(
                    StoreConfig(
                        provider=PROVIDER,
                        model=model,
                        chunk_strategy=HIERARCHICAL_STRATEGY,
                        metodo_extracao=metodo,
                        mode=mode,
                    )
                )
    if include_rerank:
        configs = configs + [
            StoreConfig(
                provider=c.provider,
                model=c.model,
                chunk_strategy=c.chunk_strategy,
                metodo_extracao=c.metodo_extracao,
                mode=c.mode,
                rerank=True,
                candidates_k_override=rerank_candidates_k,
            )
            for c in configs
        ]
    return configs


def build_rag_baseline_configs(
    *,
    query_expansion: bool = False,
    rerank_pools: tuple[int, ...] | None = None,
    exclude_revogadas_comparison: bool = False,
) -> list[StoreConfig]:
    """Escopo deliberado do smoke RAG: baseline atual + baseline com rerank.

    A matriz completa de retrieval já foi diagnosticada. Para geração, o
    primeiro teste deve responder uma pergunta menor: o baseline escolhido
    gera respostas fiéis e o rerank muda a qualidade final?

    O config com rerank usa `candidates_k_override=100` (pool 100), promovido
    a default pela Fase 2 do roadmap (`rerank_pool_pairing`: pool 100 atinge
    answer_usable_rate 0.604 vs 0.583 do pool 50), e `exclude_revogadas=True`,
    promovido a default pela Fase 1 (`revogadas_pairing`: delta_doc_recall
    +0.021, hard_broken=0; higiene factual contra citação de normas revogadas).

    Quando `query_expansion=True`, retorna 4 configs (cartesiano rerank × QE)
    para medir a interação entre rerank e query expansion no mesmo run.

    Quando `rerank_pools` é fornecido (ex.: `(50, 100)`), retorna
    `[baseline]` + uma config `rerank=True` por pool de candidatos densos,
    permitindo isolar o efeito do tamanho do pool no mesmo run (Fase 2 do
    roadmap). Mutuamente exclusivo com `query_expansion`.

    Quando `exclude_revogadas_comparison=True`, retorna 2 configs `rerank@100`
    (o default vigente) diferindo apenas em `exclude_revogadas` (False/True),
    isolando o efeito do filtro de normas revogadas no retrieval (Fase 1 do
    roadmap). Mutuamente exclusivo com `query_expansion` e `rerank_pools`.
    """
    _exclusive = [
        ("query_expansion", query_expansion),
        ("rerank_pools", rerank_pools is not None),
        ("exclude_revogadas_comparison", exclude_revogadas_comparison),
    ]
    _ativos = [nome for nome, ativo in _exclusive if ativo]
    if len(_ativos) > 1:
        raise ValueError(
            "Modos experimentais mutuamente exclusivos em "
            f"build_rag_baseline_configs: {_ativos} (use apenas um)."
        )
    baseline = StoreConfig(
        provider=PROVIDER,
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
    )
    # Fase 2 do roadmap (rerank_pool_pairing): o pareamento pool50 vs pool100
    # deu `promote` (saved=2, broken=1, delta_doc_recall=+0.042) e pool 100 é
    # o config com maior answer_usable_rate (0.604 vs 0.583). Pool 100 passou
    # a ser o default do rerank no smoke RAG.
    RERANK_DEFAULT_POOL = 100
    # Fase 1 do roadmap (revogadas_pairing): o filtro de normas revogadas deu
    # `promote` sob o critério refinado (delta_doc_recall=+0.021 E hard_broken=0;
    # os breaks são soft — doc_recall intacto, ruído de citação do gerador).
    # Motivo real: higiene factual (sem o filtro, gt-0008/gt-0030 citam normas
    # revogadas). exclude_revogadas=True passou a ser o default do rerank.
    rerank = StoreConfig(
        provider=baseline.provider,
        model=baseline.model,
        chunk_strategy=baseline.chunk_strategy,
        metodo_extracao=baseline.metodo_extracao,
        mode=baseline.mode,
        rerank=True,
        candidates_k_override=RERANK_DEFAULT_POOL,
        exclude_revogadas=True,
    )
    if rerank_pools is not None:
        return [baseline] + [
            StoreConfig(
                provider=baseline.provider,
                model=baseline.model,
                chunk_strategy=baseline.chunk_strategy,
                metodo_extracao=baseline.metodo_extracao,
                mode=baseline.mode,
                rerank=True,
                candidates_k_override=pool,
            )
            for pool in rerank_pools
        ]
    if exclude_revogadas_comparison:
        # Pareia explicitamente before (sem filtro) vs after (com filtro),
        # independentemente do default — o analyzer pareia por exclude_revogadas.
        rerank_com_revogadas = replace(rerank, exclude_revogadas=False)
        rerank_sem_revogadas = replace(rerank, exclude_revogadas=True)
        return [rerank_com_revogadas, rerank_sem_revogadas]
    if not query_expansion:
        return [baseline, rerank]
    baseline_qe = StoreConfig(
        provider=baseline.provider,
        model=baseline.model,
        chunk_strategy=baseline.chunk_strategy,
        metodo_extracao=baseline.metodo_extracao,
        mode=baseline.mode,
        query_expansion=True,
    )
    # rerank_qe deve herdar os defaults promovidos do rerank (pool 100 da F2 e
    # exclude_revogadas da F1), senão o run de QE compara contra um rerank
    # antigo, não contra o pipeline vigente.
    rerank_qe = replace(rerank, query_expansion=True)
    return [baseline, rerank, baseline_qe, rerank_qe]


def split_evaluation_questions(
    questions: Iterable[dict[str, Any]],
    *,
    evaluated_answerabilities: frozenset[str] = EVALUATED_ANSWERABILITIES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa perguntas avaliáveis das que só ficam rastreadas no relatório."""
    avaliaveis: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for question in questions:
        answerability = str(question.get("answerability") or "corpus_supported")
        if answerability in evaluated_answerabilities:
            avaliaveis.append(question)
            continue
        skipped.append(
            {
                "question_id": question.get("question_id"),
                "answerability": answerability,
                "reason": "answerability_not_evaluated",
            }
        )
    return avaliaveis, skipped


def evaluate_question(
    retriever: Retriever,
    question: dict[str, Any],
    *,
    top_k: int,
) -> dict[str, Any]:
    """Roda uma pergunta no retriever e calcula as métricas de retrieval.

    - `recall_at_k`: fração de fontes esperadas cobertas por algum chunk
       (passage-level: exige que o trecho/seção case, não só o documento)
    - `doc_recall_at_k`: fração de `document_id`s esperados cobertos por
       algum chunk (document-level: ignora section/excerpt). Diferença com
       `recall_at_k` revela problema de granularidade vs problema de
       retrieval.
    - `precision_at_k`: fração de chunks no top-k que tiveram relevância > 0
    - `mrr_at_k`: 1/posição do primeiro chunk relevante (0 se nenhum)
    - `ndcg_at_k`: nDCG ponderado pela nota de relevância (1, 2, 3)
    """
    fontes = list(question.get("relevant_sources") or [])
    expected_doc_ids = [
        str(src.get("document_id") or "") for src in fontes if src.get("document_id")
    ]

    start = perf_counter()
    retrieved = retriever.retrieve(question["question"], top_k=top_k)
    latency_ms = (perf_counter() - start) * 1000

    relevances = build_relevance_vector(retrieved, fontes)
    num_hits = sum(1 for rel in relevances if rel > 0)

    mrr = 0.0
    for idx, rel in enumerate(relevances, start=1):
        if rel > 0:
            mrr = 1.0 / idx
            break

    precision = num_hits / len(relevances) if relevances else 0.0

    return {
        "question_id": question.get("question_id"),
        "recall_at_k": source_coverage(retrieved, fontes),
        "doc_recall_at_k": doc_recall_at_k(
            retrieved, expected_doc_ids, k=top_k, groups=document_groups(fontes)
        ),
        "precision_at_k": precision,
        "mrr_at_k": mrr,
        "ndcg_at_k": ndcg_at_k(relevances, k=top_k),
        "latency_ms": latency_ms,
        "num_relevant_retrieved": num_hits,
        "num_expected_sources": len(fontes),
    }


def _default_retriever_factory(
    config: StoreConfig,
    repo_id: str | None,
    query_cache: QueryEmbeddingCache | None = None,
) -> Retriever:
    reranker = None
    if config.rerank:
        from src.rag.reranker import CohereReranker

        reranker = CohereReranker()
    exclude_situacoes = (
        frozenset({"revogada"}) if config.exclude_revogadas else None
    )
    return Retriever(
        provider=config.provider,
        model=config.model,
        chunk_strategy=config.chunk_strategy,
        metodo_extracao=config.metodo_extracao,
        mode=config.mode,
        repo_id=repo_id,
        query_cache=query_cache,
        reranker=reranker,
        candidates_k=config.candidates_k_override,
        exclude_situacoes=exclude_situacoes,
    )


def run_config(
    config: StoreConfig,
    questions: list[dict[str, Any]],
    *,
    top_k: int,
    repo_id: str | None = None,
    retriever_factory=_default_retriever_factory,
    query_cache: QueryEmbeddingCache | None = None,
) -> dict[str, Any]:
    """Carrega 1 store, roda todas as perguntas, agrega métricas."""
    retriever = retriever_factory(config, repo_id, query_cache)
    por_pergunta = [
        evaluate_question(retriever, question, top_k=top_k) for question in questions
    ]
    latencies = [row["latency_ms"] for row in por_pergunta]
    summary = latency_summary(latencies)
    if not por_pergunta:
        return {
            "provider": config.provider,
            "model": config.model,
            "chunk_strategy": config.chunk_strategy,
            "metodo_extracao": config.metodo_extracao,
            "mode": config.mode,
            "rerank": config.rerank,
            "query_expansion": config.query_expansion,
            "num_questions": 0,
            "recall_at_k": 0.0,
            "doc_recall_at_k": 0.0,
            "precision_at_k": 0.0,
            "mrr_at_k": 0.0,
            "ndcg_at_k": 0.0,
            "latency_avg_ms": summary["latency_avg"],
            "latency_p95_ms": summary["latency_p95"],
            "per_question": [],
        }
    return {
        "provider": config.provider,
        "model": config.model,
        "chunk_strategy": config.chunk_strategy,
        "metodo_extracao": config.metodo_extracao,
        "mode": config.mode,
        "rerank": config.rerank,
        "query_expansion": config.query_expansion,
        "num_questions": len(por_pergunta),
        "recall_at_k": mean(row["recall_at_k"] for row in por_pergunta),
        "doc_recall_at_k": mean(row["doc_recall_at_k"] for row in por_pergunta),
        "precision_at_k": mean(row["precision_at_k"] for row in por_pergunta),
        "mrr_at_k": mean(row["mrr_at_k"] for row in por_pergunta),
        "ndcg_at_k": mean(row["ndcg_at_k"] for row in por_pergunta),
        "latency_avg_ms": summary["latency_avg"],
        "latency_p95_ms": summary["latency_p95"],
        "per_question": por_pergunta,
    }


def _citation_accuracy_from_response(
    response: dict[str, Any],
    relevances: list[int],
) -> float:
    """Precisão das citações: das fontes citadas, quantas eram relevantes."""
    contexts = list(response.get("contexts") or [])
    citations = {str(citation) for citation in response.get("citations", [])}
    if not citations:
        return 0.0

    relevant_labels = {
        str(context.get("citation_label"))
        for context, rel in zip(contexts, relevances)
        if rel > 0 and context.get("citation_label")
    }
    if not relevant_labels:
        return 0.0
    return len(citations & relevant_labels) / len(citations)


def _answer_usable(
    *,
    recall_at_k: float,
    citation_accuracy_value: float,
    answer_correctness: Any,
) -> bool:
    """Combina contexto, citação e resposta final em um gate único.

    Sem `answer_correctness` do juiz LLM, a resposta não pode ser marcada como
    usável: falta evidência sobre qualidade final, mesmo que o retrieval pareça
    bom.
    """
    if answer_correctness is None:
        return False
    return (
        recall_at_k > 0
        and citation_accuracy_value >= ANSWER_USABLE_MIN_CITATION_ACCURACY
        and float(answer_correctness) >= ANSWER_USABLE_MIN_ANSWER_CORRECTNESS
    )


def _rag_failure_type(
    *,
    answer_usable: bool,
    recall_at_k: float,
    doc_recall_at_k_value: float,
    citation_accuracy_value: float,
    answer_correctness: Any,
    generator_status: Any,
) -> str:
    """Classifica a primeira área que precisa de diagnóstico humano."""
    if answer_usable:
        return "usable"
    if generator_status not in (None, "ok"):
        return "generator_failure"
    if recall_at_k <= 0 and doc_recall_at_k_value <= 0:
        return "retrieval_document_failure"
    if recall_at_k <= 0 and doc_recall_at_k_value > 0:
        return "retrieval_passage_failure"
    if answer_correctness is None:
        return "llm_judge_missing"

    citation_bad = citation_accuracy_value < ANSWER_USABLE_MIN_CITATION_ACCURACY
    answer_bad = float(answer_correctness) < ANSWER_USABLE_MIN_ANSWER_CORRECTNESS
    if citation_bad and answer_bad:
        return "citation_and_answer_failure"
    if citation_bad:
        return "citation_failure"
    if answer_bad:
        return "answer_quality_failure"
    return "unknown_failure"


def evaluate_question_rag(
    rag,
    question: dict[str, Any],
    *,
    top_k: int,
    llm_metrics_fn=optional_llm_metrics,
) -> dict[str, Any]:
    """Roda uma pergunta no RAG e calcula retrieval + métricas de resposta."""
    fontes = list(question.get("relevant_sources") or [])
    expected_doc_ids = [
        str(src.get("document_id") or "") for src in fontes if src.get("document_id")
    ]

    response = rag.query(question["question"], top_k=top_k)
    contexts = list(response.get("contexts") or [])
    relevances = build_relevance_vector(contexts, fontes)
    num_hits = sum(1 for rel in relevances if rel > 0)

    mrr = 0.0
    for idx, rel in enumerate(relevances, start=1):
        if rel > 0:
            mrr = 1.0 / idx
            break

    precision = num_hits / len(relevances) if relevances else 0.0
    llm_metrics = llm_metrics_fn(
        answer=str(response.get("answer") or ""),
        contexts=contexts,
        reference=(
            question.get("expected_answer")
            or question.get("reference_answer")
            or question.get("answer_reference")
        ),
    )
    recall = source_coverage(contexts, fontes)
    doc_recall = doc_recall_at_k(
        contexts, expected_doc_ids, k=top_k, groups=document_groups(fontes)
    )
    citation_acc = _citation_accuracy_from_response(response, relevances)
    answer_is_usable = _answer_usable(
        recall_at_k=recall,
        citation_accuracy_value=citation_acc,
        answer_correctness=llm_metrics.get("answer_correctness"),
    )
    failure_type = _rag_failure_type(
        answer_usable=answer_is_usable,
        recall_at_k=recall,
        doc_recall_at_k_value=doc_recall,
        citation_accuracy_value=citation_acc,
        answer_correctness=llm_metrics.get("answer_correctness"),
        generator_status=response.get("generator_status"),
    )

    return {
        "question_id": question.get("question_id"),
        "answer": response.get("answer"),
        "citations": response.get("citations", []),
        "recall_at_k": recall,
        "doc_recall_at_k": doc_recall,
        "precision_at_k": precision,
        "mrr_at_k": mrr,
        "ndcg_at_k": ndcg_at_k(relevances, k=top_k),
        "latency_ms": response.get("latency_ms"),
        "num_relevant_retrieved": num_hits,
        "num_expected_sources": len(fontes),
        "citation_accuracy": citation_acc,
        "answer_usable": answer_is_usable,
        "failure_type": failure_type,
        "generator_status": response.get("generator_status"),
        "generator_error": response.get("generator_error"),
        "expanded_query": response.get("expanded_query"),
        "query_expansion_status": response.get("query_expansion_status"),
        "query_expansion_error": response.get("query_expansion_error"),
        **llm_metrics,
    }


def _default_rag_factory(
    config: StoreConfig,
    repo_id: str | None,
    query_cache: QueryEmbeddingCache | None = None,
) -> NaiveRAG:
    retriever = _default_retriever_factory(config, repo_id, query_cache)
    expander = QueryExpander() if config.query_expansion else None
    return NaiveRAG(
        retriever,
        strategy=config.label,
        generator=generate_llm_answer,
        query_expander=expander,
    )


def _mean_present(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return mean(float(value) for value in values)


def _count_status(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get(key) or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _failure_next_focus(failure_type: str) -> str:
    mapping = {
        "retrieval_document_failure": "query_expansion_or_retrieval",
        "retrieval_passage_failure": "chunking_rerank_or_matching",
        "citation_failure": "prompt_or_citation_selection",
        "answer_quality_failure": "prompt_generator_or_ground_truth",
        "citation_and_answer_failure": "prompt_generator_or_context_use",
        "generator_failure": "generator_runtime",
        "llm_judge_missing": "rerun_with_llm_judge",
        "unknown_failure": "manual_review",
    }
    return mapping.get(failure_type, "manual_review")


def build_rag_failure_analysis(result: BenchmarkResult) -> dict[str, Any]:
    """Consolida falhas RAG em um formato pequeno para triagem pós-smoke."""
    configs: list[dict[str, Any]] = []
    for _, row in result.metrics.iterrows():
        label_suffix = "+rerank" if bool(row.get("rerank")) else ""
        label = (
            f"{row.get('model')}|{row.get('chunk_strategy')}|"
            f"{row.get('metodo_extracao')}|{row.get('mode')}{label_suffix}"
        )
        failures = []
        for question in row.get("per_question") or []:
            if question.get("answer_usable"):
                continue
            failure_type = str(question.get("failure_type") or "unknown_failure")
            failures.append(
                {
                    "question_id": question.get("question_id"),
                    "failure_type": failure_type,
                    "next_focus": _failure_next_focus(failure_type),
                    "recall_at_k": question.get("recall_at_k"),
                    "doc_recall_at_k": question.get("doc_recall_at_k"),
                    "citation_accuracy": question.get("citation_accuracy"),
                    "answer_correctness": question.get("answer_correctness"),
                    "faithfulness": question.get("faithfulness"),
                    "generator_status": question.get("generator_status"),
                    "llm_status": question.get("llm_status"),
                }
            )
        configs.append(
            {
                "label": label,
                "answer_usable_rate": row.get("answer_usable_rate"),
                "failure_type_counts": row.get("failure_type_counts") or {},
                "num_failures": len(failures),
                "failures": failures,
            }
        )
    return {
        "metric_definition": {
            "answer_usable": (
                "recall_at_k > 0 and citation_accuracy >= 0.5 and "
                "answer_correctness >= 0.8"
            ),
            "failure_types": {
                "retrieval_document_failure": (
                    "documento esperado nao aparece no top-k"
                ),
                "retrieval_passage_failure": (
                    "documento aparece, mas trecho esperado nao casa"
                ),
                "citation_failure": (
                    "contexto e resposta passam, mas citacao fica abaixo do piso"
                ),
                "answer_quality_failure": (
                    "contexto e citacao passam, mas resposta fica abaixo do piso"
                ),
                "citation_and_answer_failure": (
                    "contexto passa, mas citacao e resposta falham"
                ),
                "generator_failure": "gerador falhou ou usou fallback com erro",
                "llm_judge_missing": "juiz LLM ausente; usabilidade inconclusiva",
                "unknown_failure": "falha residual para revisao manual",
            },
        },
        "configs": configs,
    }


# -----------------------------------------------------------------------------
# Pareamento baseline vs baseline+rerank
# -----------------------------------------------------------------------------


RERANK_PAIRING_BUCKETS = (
    "saved_by_rerank",
    "broken_by_rerank",
    "stable_pass",
    "stable_fail_same_type",
    "stable_fail_changed_type",
)
RERANK_PROMOTE_SAVED_BROKEN_RATIO = 2
RERANK_PROMOTE_MAX_DELTA_DOC_FAILURE = 1


def _row_per_question_dict(row: Any) -> dict[str, dict[str, Any]]:
    """Indexa per_question por question_id em dict. Erra se houver duplicata."""
    indexed: dict[str, dict[str, Any]] = {}
    for question in row.get("per_question") or []:
        qid = str(question.get("question_id"))
        if qid in indexed:
            raise ValueError(
                f"question_id duplicado dentro de uma config: {qid!r}"
            )
        indexed[qid] = question
    return indexed


def _pairing_question_entry(
    qid: str,
    baseline_q: dict[str, Any],
    rerank_q: dict[str, Any],
) -> dict[str, Any]:
    return {
        "question_id": qid,
        "baseline_failure_type": str(
            baseline_q.get("failure_type") or "unknown_failure"
        ),
        "rerank_failure_type": str(rerank_q.get("failure_type") or "unknown_failure"),
        "recall_baseline": baseline_q.get("recall_at_k"),
        "recall_rerank": rerank_q.get("recall_at_k"),
        "doc_recall_baseline": baseline_q.get("doc_recall_at_k"),
        "doc_recall_rerank": rerank_q.get("doc_recall_at_k"),
    }


def build_rag_rerank_pairing(result: BenchmarkResult) -> dict[str, Any]:
    """Pareia `per_question` entre `rerank=False` e `rerank=True` por
    `question_id` e classifica cada pergunta em um bucket.

    Buckets:
      - `saved_by_rerank`: baseline não-usável, rerank usável.
      - `broken_by_rerank`: baseline usável, rerank não-usável.
      - `stable_pass`: ambos usáveis.
      - `stable_fail_same_type`: ambos não-usáveis com mesmo `failure_type`.
      - `stable_fail_changed_type`: ambos não-usáveis com `failure_type`
        diferente (mudança diagnóstica do que travou a pergunta).

    Levanta `ValueError` se faltar uma das duas configs (`rerank` False/True)
    ou se o conjunto de `question_id` for assimétrico entre as duas.
    """
    baseline_row = None
    rerank_row = None
    for _, row in result.metrics.iterrows():
        if bool(row.get("rerank")):
            if rerank_row is not None:
                raise ValueError(
                    "rerank pairing exige exatamente uma config rerank=True; "
                    "encontrei mais de uma."
                )
            rerank_row = row
        else:
            if baseline_row is not None:
                raise ValueError(
                    "rerank pairing exige exatamente uma config rerank=False; "
                    "encontrei mais de uma."
                )
            baseline_row = row
    if baseline_row is None or rerank_row is None:
        raise ValueError(
            "rerank pairing requer ambos configs rerank=False e rerank=True "
            "no mesmo BenchmarkResult."
        )

    baseline_by_qid = _row_per_question_dict(baseline_row)
    rerank_by_qid = _row_per_question_dict(rerank_row)

    only_baseline = sorted(set(baseline_by_qid) - set(rerank_by_qid))
    only_rerank = sorted(set(rerank_by_qid) - set(baseline_by_qid))
    if only_baseline or only_rerank:
        raise ValueError(
            "rerank pairing requer mesmo conjunto de question_id em ambos "
            f"configs. Faltam no rerank: {only_baseline}; faltam no baseline: "
            f"{only_rerank}."
        )

    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in RERANK_PAIRING_BUCKETS}
    for qid in sorted(baseline_by_qid):
        baseline_q = baseline_by_qid[qid]
        rerank_q = rerank_by_qid[qid]
        baseline_ok = bool(baseline_q.get("answer_usable"))
        rerank_ok = bool(rerank_q.get("answer_usable"))
        entry = _pairing_question_entry(qid, baseline_q, rerank_q)

        if baseline_ok and rerank_ok:
            buckets["stable_pass"].append(entry)
        elif not baseline_ok and rerank_ok:
            buckets["saved_by_rerank"].append(entry)
        elif baseline_ok and not rerank_ok:
            buckets["broken_by_rerank"].append(entry)
        else:
            if entry["baseline_failure_type"] == entry["rerank_failure_type"]:
                buckets["stable_fail_same_type"].append(entry)
            else:
                buckets["stable_fail_changed_type"].append(entry)

    baseline_counts = dict(baseline_row.get("failure_type_counts") or {})
    rerank_counts = dict(rerank_row.get("failure_type_counts") or {})
    delta_doc_failure = rerank_counts.get(
        "retrieval_document_failure", 0
    ) - baseline_counts.get("retrieval_document_failure", 0)

    saved_count = len(buckets["saved_by_rerank"])
    broken_count = len(buckets["broken_by_rerank"])
    threshold = RERANK_PROMOTE_SAVED_BROKEN_RATIO * broken_count

    reasons: list[str] = []
    if saved_count < threshold:
        reasons.append(
            f"saved={saved_count} < {RERANK_PROMOTE_SAVED_BROKEN_RATIO}*broken="
            f"{threshold}"
        )
    if delta_doc_failure > RERANK_PROMOTE_MAX_DELTA_DOC_FAILURE:
        reasons.append(
            f"delta_doc_failure=+{delta_doc_failure} > "
            f"+{RERANK_PROMOTE_MAX_DELTA_DOC_FAILURE}"
        )
    verdict = "promote" if not reasons else "keep_optional"

    return {
        "buckets": {
            name: {"count": len(items), "questions": items}
            for name, items in buckets.items()
        },
        "summary": {
            "saved_count": saved_count,
            "broken_count": broken_count,
            "net_delta": saved_count - broken_count,
            "delta_doc_failure": delta_doc_failure,
            "rerank_candidates_k": (
                None
                if rerank_row.get("candidates_k") is None
                or pd.isna(rerank_row.get("candidates_k"))
                else int(rerank_row.get("candidates_k"))
            ),
            "rerank_exclude_revogadas": bool(
                rerank_row.get("exclude_revogadas") or False
            ),
            "baseline_answer_usable_rate": (
                None
                if baseline_row.get("answer_usable_rate") is None
                else float(baseline_row.get("answer_usable_rate"))
            ),
            "rerank_answer_usable_rate": (
                None
                if rerank_row.get("answer_usable_rate") is None
                else float(rerank_row.get("answer_usable_rate"))
            ),
            "baseline_failure_type_counts": baseline_counts,
            "rerank_failure_type_counts": rerank_counts,
        },
        "decision_rule": {
            "rule": (
                "promover rerank a default SE saved_by_rerank >= "
                f"{RERANK_PROMOTE_SAVED_BROKEN_RATIO} * broken_by_rerank "
                f"E delta_doc_failure <= +{RERANK_PROMOTE_MAX_DELTA_DOC_FAILURE}"
            ),
            "saved": saved_count,
            "broken": broken_count,
            "threshold_broken_x_ratio": threshold,
            "delta_doc_failure": delta_doc_failure,
            "max_delta_doc_failure": RERANK_PROMOTE_MAX_DELTA_DOC_FAILURE,
            "verdict": verdict,
            "reasons": reasons,
        },
    }


def render_rag_rerank_pairing_md(pairing: dict[str, Any]) -> str:
    """Renderiza pairing em markdown legível com tabela, listas e veredito."""
    buckets = pairing.get("buckets") or {}
    summary = pairing.get("summary") or {}
    decision = pairing.get("decision_rule") or {}

    def _rate(key: str) -> str:
        value = summary.get(key)
        return "n/d" if value is None else f"{float(value):.3f}"

    lines = [
        "# Pareamento rerank vs baseline",
        "",
    ]

    # Nota dinâmica: após F1/F2, a config "rerank" carrega os defaults
    # promovidos (pool 100 + filtro de revogadas), então "rerank" aqui é o
    # pipeline completo — não rerank isolado. Só emite quando há default
    # promovido (filtro ON e/ou pool != 50), preservando o sentido literal
    # para runs antigos/puros.
    pool = summary.get("rerank_candidates_k")
    filtro_on = bool(summary.get("rerank_exclude_revogadas"))
    pool_promovido = pool is not None and pool != 50
    if filtro_on or pool_promovido:
        partes = []
        if pool_promovido:
            partes.append(f"pool {pool} (F2)")
        if filtro_on:
            partes.append("filtro de revogadas (F1)")
        lines.extend(
            [
                f"> **Nota:** a config \"rerank\" reflete os defaults promovidos "
                f"— {' + '.join(partes)}. Este pareamento mede **baseline cru "
                "vs pipeline completo**, não rerank isolado.",
                "",
            ]
        )

    lines.extend(
        [
            "## Resumo",
            "",
            "| Bucket | Count |",
            "|---|---:|",
        ]
    )
    for name in RERANK_PAIRING_BUCKETS:
        count = (buckets.get(name) or {}).get("count", 0)
        lines.append(f"| `{name}` | {count} |")
    lines.extend(
        [
            "",
            (
                f"`answer_usable_rate`: baseline {_rate('baseline_answer_usable_rate')}"
                f" -> rerank {_rate('rerank_answer_usable_rate')} "
                f"(net_delta={summary.get('net_delta', 0):+d})"
            ),
            (
                "`retrieval_document_failure`: baseline "
                f"{(summary.get('baseline_failure_type_counts') or {}).get('retrieval_document_failure', 0)}"
                " -> rerank "
                f"{(summary.get('rerank_failure_type_counts') or {}).get('retrieval_document_failure', 0)}"
                f" (delta={summary.get('delta_doc_failure', 0):+d})"
            ),
            "",
        ]
    )

    def _section(title: str, name: str, arrow_left: str, arrow_right: str) -> None:
        items = (buckets.get(name) or {}).get("questions") or []
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_Nenhuma pergunta neste bucket._")
            lines.append("")
            return
        for item in items:
            left = item.get(arrow_left)
            right = item.get(arrow_right)
            lines.append(f"- `{item['question_id']}`: {left} -> {right}")
        lines.append("")

    _section(
        "Salvas pelo rerank",
        "saved_by_rerank",
        "baseline_failure_type",
        "rerank_failure_type",
    )
    _section(
        "Quebradas pelo rerank",
        "broken_by_rerank",
        "baseline_failure_type",
        "rerank_failure_type",
    )
    _section(
        "Falhas estáveis com tipo diferente",
        "stable_fail_changed_type",
        "baseline_failure_type",
        "rerank_failure_type",
    )

    lines.extend(
        [
            "## Veredito",
            "",
            f"Regra: {decision.get('rule')}",
            "",
            f"- `saved`: {decision.get('saved')}",
            f"- `broken`: {decision.get('broken')}",
            (
                f"- `threshold` ({RERANK_PROMOTE_SAVED_BROKEN_RATIO}*broken): "
                f"{decision.get('threshold_broken_x_ratio')}"
            ),
            f"- `delta_doc_failure`: {decision.get('delta_doc_failure'):+d}",
            f"- `veredito`: **{decision.get('verdict')}**",
        ]
    )
    reasons = decision.get("reasons") or []
    if reasons:
        lines.append("- `razões`:")
        for reason in reasons:
            lines.append(f"  - {reason}")
    lines.append("")
    return "\n".join(lines)


def load_benchmark_result_from_per_question_json(
    path: str | Path,
) -> BenchmarkResult:
    """Reconstrói um `BenchmarkResult` a partir de um `per_question.json`
    já gerado, sem rodar LLM. Reagrega `failure_type_counts` e
    `answer_usable_rate` a partir do `per_question` para não depender de
    campos que possam não estar no JSON antigo.

    Útil para regenerar artefatos derivados (failure_analysis, rerank_pairing)
    quando a lógica muda, sem custo de chamada LLM.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    results = data.get("results") or []
    if not results:
        raise ValueError(
            f"per_question.json em {path} não tem chave `results` com dados."
        )

    linhas: list[dict[str, Any]] = []
    for config in results:
        per_question = list(config.get("per_question") or [])
        failure_counts = _count_values(per_question, "failure_type")
        answer_usable_rate = (
            mean(1.0 if q.get("answer_usable") else 0.0 for q in per_question)
            if per_question
            else 0.0
        )
        linhas.append(
            {
                "provider": config.get("provider", PROVIDER),
                "model": config.get("model"),
                "chunk_strategy": config.get("chunk_strategy"),
                "metodo_extracao": config.get("metodo_extracao"),
                "mode": config.get("mode"),
                "rerank": bool(config.get("rerank")),
                "candidates_k": config.get("candidates_k"),
                "query_expansion": bool(config.get("query_expansion") or False),
                "exclude_revogadas": bool(config.get("exclude_revogadas") or False),
                "per_question": per_question,
                "failure_type_counts": failure_counts,
                "answer_usable_rate": answer_usable_rate,
                "llm_status_counts": config.get("llm_status_counts") or {},
                "generator_status_counts": config.get("generator_status_counts") or {},
                "num_questions": len(per_question),
            }
        )

    return BenchmarkResult(
        metrics=pd.DataFrame(linhas),
        skipped_questions=list(data.get("skipped_questions") or []),
        cache_stats=dict(data.get("cache_stats") or {}),
    )


def run_rag_config(
    config: StoreConfig,
    questions: list[dict[str, Any]],
    *,
    top_k: int,
    repo_id: str | None = None,
    rag_factory=_default_rag_factory,
    query_cache: QueryEmbeddingCache | None = None,
    llm_metrics_fn=optional_llm_metrics,
) -> dict[str, Any]:
    """Carrega 1 RAG, gera respostas e agrega métricas de retrieval/resposta."""
    rag = rag_factory(config, repo_id, query_cache)
    por_pergunta = [
        evaluate_question_rag(
            rag,
            question,
            top_k=top_k,
            llm_metrics_fn=llm_metrics_fn,
        )
        for question in questions
    ]
    latencies = [
        row["latency_ms"] for row in por_pergunta if row.get("latency_ms") is not None
    ]
    summary = latency_summary(latencies)

    base = {
        "provider": config.provider,
        "model": config.model,
        "chunk_strategy": config.chunk_strategy,
        "metodo_extracao": config.metodo_extracao,
        "mode": config.mode,
        "rerank": config.rerank,
        "candidates_k": config.candidates_k_override,
        "query_expansion": config.query_expansion,
        "exclude_revogadas": config.exclude_revogadas,
        "num_questions": len(por_pergunta),
        "latency_avg_ms": summary["latency_avg"],
        "latency_p95_ms": summary["latency_p95"],
        "per_question": por_pergunta,
        "llm_status_counts": _count_status(por_pergunta, "llm_status"),
        "generator_status_counts": _count_status(por_pergunta, "generator_status"),
    }
    if not por_pergunta:
        return {
            **base,
            "recall_at_k": 0.0,
            "doc_recall_at_k": 0.0,
            "precision_at_k": 0.0,
            "mrr_at_k": 0.0,
            "ndcg_at_k": 0.0,
            "faithfulness_avg": None,
            "answer_correctness_avg": None,
            "citation_accuracy_avg": 0.0,
            "answer_usable_rate": 0.0,
            "failure_type_counts": {},
        }

    return {
        **base,
        "recall_at_k": mean(row["recall_at_k"] for row in por_pergunta),
        "doc_recall_at_k": mean(row["doc_recall_at_k"] for row in por_pergunta),
        "precision_at_k": mean(row["precision_at_k"] for row in por_pergunta),
        "mrr_at_k": mean(row["mrr_at_k"] for row in por_pergunta),
        "ndcg_at_k": mean(row["ndcg_at_k"] for row in por_pergunta),
        "faithfulness_avg": _mean_present(por_pergunta, "faithfulness"),
        "answer_correctness_avg": _mean_present(por_pergunta, "answer_correctness"),
        "citation_accuracy_avg": mean(row["citation_accuracy"] for row in por_pergunta),
        "answer_usable_rate": mean(
            1.0 if row.get("answer_usable") else 0.0 for row in por_pergunta
        ),
        "failure_type_counts": _count_values(por_pergunta, "failure_type"),
    }


def run_rag_benchmark(
    questions: list[dict[str, Any]],
    *,
    top_k: int = 10,
    configs: Iterable[StoreConfig] | None = None,
    repo_id: str | None = None,
    rag_factory=_default_rag_factory,
    query_cache: QueryEmbeddingCache | None = None,
    llm_metrics_fn=optional_llm_metrics,
) -> BenchmarkResult:
    """Roda o smoke RAG nas configs selecionadas."""
    if configs is None:
        configs = build_rag_baseline_configs()
    configs_list = list(configs)
    questions_list = list(questions)
    evaluation_questions, skipped_questions = split_evaluation_questions(questions_list)

    if query_cache is None:
        query_cache = QueryEmbeddingCache()

    linhas = []
    for config in configs_list:
        print(f"  Avaliando RAG {config.label} ...")
        linha = run_rag_config(
            config,
            evaluation_questions,
            top_k=top_k,
            repo_id=repo_id,
            rag_factory=rag_factory,
            query_cache=query_cache,
            llm_metrics_fn=llm_metrics_fn,
        )
        linha["num_questions_total"] = len(questions_list)
        linha["num_questions_evaluated"] = len(evaluation_questions)
        linha["num_questions_skipped"] = len(skipped_questions)
        linhas.append(linha)

    print(f"  Query cache: {query_cache.stats}")
    return BenchmarkResult(
        metrics=pd.DataFrame(linhas),
        skipped_questions=skipped_questions,
        cache_stats=dict(query_cache.stats),
    )


def run_full_benchmark(
    questions: list[dict[str, Any]],
    *,
    top_k: int = 10,
    configs: Iterable[StoreConfig] | None = None,
    repo_id: str | None = None,
    retriever_factory=_default_retriever_factory,
    query_cache: QueryEmbeddingCache | None = None,
    max_workers: int = 1,
) -> BenchmarkResult:
    """Roda todas as configs e devolve o resultado completo do benchmark.

    `result.metrics` é a tabela principal: cada linha é uma config, com
    métricas médias e latência agregada. A coluna `per_question` guarda o
    detalhamento por pergunta para análise post-hoc.

    `result.skipped_questions` mantém perguntas fora do agregado, como
    `source_only`, sem depender de `DataFrame.attrs`, que é frágil em cópias,
    merges e serializações.

    Quando `query_cache` é passado, o mesmo cache é compartilhado entre todos
    os retrievers — embeddings de query iguais (50 perguntas × 2 modelos) são
    computados uma única vez.

    `max_workers > 1` paraleliza as configs em ThreadPool: cada worker carrega
    sua própria store e roda as perguntas. ThreadPool (não ProcessPool) porque:
    (a) o gargalo é I/O — download/leitura de store + chamada HTTP da OpenAI;
    (b) o cache compartilhado funciona naturalmente entre threads;
    (c) consumo de RAM é proporcional aos workers ativos, não fixo.
    """
    if configs is None:
        configs = build_store_configs()
    configs_list = list(configs)
    questions_list = list(questions)
    evaluation_questions, skipped_questions = split_evaluation_questions(questions_list)

    if query_cache is None:
        query_cache = QueryEmbeddingCache()

    def _run(config: StoreConfig) -> dict[str, Any]:
        print(f"  Avaliando {config.label} ...")
        return run_config(
            config,
            evaluation_questions,
            top_k=top_k,
            repo_id=repo_id,
            retriever_factory=retriever_factory,
            query_cache=query_cache,
        )

    if max_workers <= 1:
        linhas = [_run(config) for config in configs_list]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            linhas = list(pool.map(_run, configs_list))

    print(f"  Query cache: {query_cache.stats}")
    for linha in linhas:
        linha["num_questions_total"] = len(questions_list)
        linha["num_questions_evaluated"] = len(evaluation_questions)
        linha["num_questions_skipped"] = len(skipped_questions)
    df = pd.DataFrame(linhas)
    return BenchmarkResult(
        metrics=df,
        skipped_questions=skipped_questions,
        cache_stats=dict(query_cache.stats),
    )


# -----------------------------------------------------------------------------
# Runner antigo (mantido para uso por código de geração já existente)
# -----------------------------------------------------------------------------


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("questions", []))
    return list(data)


def run_benchmark(
    rag, questions: list[dict[str, Any]], *, top_k: int = 5
) -> dict[str, Any]:
    """Runner legado para `NaiveRAG` (camada de geração — fora do escopo do
    benchmark de retrieval).
    """
    rows = []
    for question in questions:
        response = rag.query(question["pergunta"], top_k=top_k)
        row = {
            "id": question["id"],
            "strategy": response["strategy"],
            **evaluate_response(response, question, k=top_k),
        }
        rows.append(row)

    latencies = [row["latency_ms"] for row in rows if row.get("latency_ms") is not None]
    return {
        "strategy": getattr(rag, "strategy", "unknown"),
        "num_questions": len(rows),
        "rows": rows,
        **latency_summary(latencies),
    }
