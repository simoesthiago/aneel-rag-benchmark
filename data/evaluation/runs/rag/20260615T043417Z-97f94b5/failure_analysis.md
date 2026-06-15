# Diagnóstico de usabilidade RAG

## Definição

`answer_usable = recall_at_k > 0 and citation_accuracy >= 0.5 and answer_correctness >= 0.8`.

Essa métrica separa resposta fiel ao contexto errado de resposta realmente útil para o usuário final.

## text-embedding-3-large|fixed-size|markdown|flat

- `answer_usable_rate`: 0.6041666666666666
- `num_failures`: 19
- `failure_type_counts`: {'usable': 29, 'citation_and_answer_failure': 3, 'answer_quality_failure': 2, 'retrieval_document_failure': 6, 'retrieval_passage_failure': 3, 'citation_failure': 5}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0002 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.0 | 0.72 |
| gt-0003 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.6666666666666666 | 0.78 |
| gt-0007 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.02 |
| gt-0012 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.08 |
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.18 |
| gt-0017 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.95 |
| gt-0019 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.2 | 0.92 |
| gt-0022 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.3333333333333333 | 0.22 |
| gt-0023 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 0.99 |
| gt-0024 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 1.0 |
| gt-0025 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.99 |
| gt-0026 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.97 |
| gt-0027 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.08 |
| gt-0028 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.0 | 0.72 |
| gt-0029 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.95 |
| gt-0030 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.88 |
| gt-0034 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.88 |
| gt-0039 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.97 |
| gt-0049 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.93 |

## text-embedding-3-large|fixed-size|texto|flat

- `answer_usable_rate`: 0.5625
- `num_failures`: 21
- `failure_type_counts`: {'answer_quality_failure': 3, 'usable': 27, 'retrieval_passage_failure': 4, 'retrieval_document_failure': 6, 'citation_failure': 6, 'citation_and_answer_failure': 2}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0001 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0002 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.78 |
| gt-0005 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.06 |
| gt-0007 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.02 |
| gt-0010 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 1.0 |
| gt-0012 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.05 |
| gt-0014 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.16666666666666666 | 0.72 |
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.18 |
| gt-0017 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.95 |
| gt-0019 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.22 |
| gt-0020 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.25 | 0.99 |
| gt-0022 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.25 | 0.88 |
| gt-0023 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.0 | 0.72 |
| gt-0024 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.2 | 0.97 |
| gt-0025 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.96 |
| gt-0026 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.97 |
| gt-0027 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.22 |
| gt-0028 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.2 | 0.86 |
| gt-0029 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.95 |
| gt-0030 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.96 |
| gt-0049 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.92 |

## text-embedding-3-large|fixed-size|markdown|flat+rerank

- `answer_usable_rate`: 0.7708333333333334
- `num_failures`: 11
- `failure_type_counts`: {'usable': 37, 'answer_quality_failure': 3, 'retrieval_passage_failure': 1, 'citation_failure': 5, 'citation_and_answer_failure': 1, 'retrieval_document_failure': 1}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0002 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0009 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.74 |
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.6666666666666666 | 0.12 |
| gt-0017 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.88 |
| gt-0019 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.96 |
| gt-0020 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.96 |
| gt-0022 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.3333333333333333 | 0.18 |
| gt-0030 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.99 |
| gt-0035 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.95 |
| gt-0039 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.2222222222222222 | 1.0 |
| gt-0049 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.42 |

## text-embedding-3-large|fixed-size|texto|flat+rerank

- `answer_usable_rate`: 0.8125
- `num_failures`: 9
- `failure_type_counts`: {'answer_quality_failure': 3, 'usable': 39, 'citation_failure': 3, 'citation_and_answer_failure': 1, 'retrieval_document_failure': 2}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0001 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0002 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0005 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.88 |
| gt-0015 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.3333333333333333 | 0.18 |
| gt-0017 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.95 |
| gt-0019 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.25 | 0.88 |
| gt-0022 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.22 |
| gt-0039 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.25 | 0.97 |
| gt-0049 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.78 |
