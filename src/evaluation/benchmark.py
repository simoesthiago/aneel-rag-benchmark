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
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Iterable

import pandas as pd

from src.embeddings.cache import QueryEmbeddingCache
from src.evaluation.matching import build_relevance_vector, source_coverage
from src.evaluation.metrics import (
    doc_recall_at_k,
    evaluate_response,
    latency_summary,
    ndcg_at_k,
)
from src.rag.retriever import Retriever, RetrieverMode

PROVIDER = "openai"
EMBEDDING_MODELS = ("text-embedding-3-large", "text-embedding-3-small")
METODOS_EXTRACAO = ("markdown", "texto")
NON_HIERARCHICAL_STRATEGIES = ("fixed-size", "article-aware")
HIERARCHICAL_STRATEGY = "hierarchical-child"
EVALUATED_ANSWERABILITIES = frozenset({"corpus_supported"})


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

    @property
    def label(self) -> str:
        suffix = "+rerank" if self.rerank else ""
        if self.rerank and self.candidates_k_override:
            suffix += f"@pool{self.candidates_k_override}"
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


def split_evaluation_questions(
    questions: Iterable[dict[str, Any]],
    *,
    evaluated_answerabilities: frozenset[str] = EVALUATED_ANSWERABILITIES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa perguntas avaliáveis das que só ficam rastreadas no relatório."""
    avaliaveis: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for question in questions:
        answerability = str(
            question.get("answerability") or "corpus_supported"
        )
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
        str(src.get("document_id") or "")
        for src in fontes
        if src.get("document_id")
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
            retrieved, expected_doc_ids, k=top_k
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
        evaluate_question(retriever, question, top_k=top_k)
        for question in questions
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
        "num_questions": len(por_pergunta),
        "recall_at_k": mean(row["recall_at_k"] for row in por_pergunta),
        "doc_recall_at_k": mean(
            row["doc_recall_at_k"] for row in por_pergunta
        ),
        "precision_at_k": mean(row["precision_at_k"] for row in por_pergunta),
        "mrr_at_k": mean(row["mrr_at_k"] for row in por_pergunta),
        "ndcg_at_k": mean(row["ndcg_at_k"] for row in por_pergunta),
        "latency_avg_ms": summary["latency_avg"],
        "latency_p95_ms": summary["latency_p95"],
        "per_question": por_pergunta,
    }


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
    evaluation_questions, skipped_questions = split_evaluation_questions(
        questions_list
    )

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

    latencies = [
        row["latency_ms"]
        for row in rows
        if row.get("latency_ms") is not None
    ]
    return {
        "strategy": getattr(rag, "strategy", "unknown"),
        "num_questions": len(rows),
        "rows": rows,
        **latency_summary(latencies),
    }
