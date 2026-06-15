# Diagnóstico de usabilidade RAG

## Definição

`answer_usable = recall_at_k > 0 and citation_accuracy >= 0.5 and answer_correctness >= 0.8`.

Essa métrica separa resposta fiel ao contexto errado de resposta realmente útil para o usuário final.

## text-embedding-3-large|fixed-size|texto|flat

- `answer_usable_rate`: 0.625
- `num_failures`: 18
- `failure_type_counts`: {'answer_quality_failure': 4, 'citation_failure': 4, 'usable': 30, 'retrieval_passage_failure': 3, 'retrieval_document_failure': 6, 'citation_and_answer_failure': 1}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0001 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0002 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 0.86 |
| gt-0005 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.06 |
| gt-0007 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.0 |
| gt-0010 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 1.0 |
| gt-0012 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.05 |
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.12 |
| gt-0017 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.92 |
| gt-0022 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.42 |
| gt-0023 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.0 | 0.72 |
| gt-0025 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 1.0 |
| gt-0026 | retrieval_passage_failure | chunking_rerank_or_matching | 0.0 | 1.0 | 0.0 | 0.95 |
| gt-0027 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.28 |
| gt-0028 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.0 | 0.92 |
| gt-0029 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.95 |
| gt-0030 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.96 |
| gt-0046 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.78 |
| gt-0049 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.92 |

## text-embedding-3-large|fixed-size|texto|flat+rerank

- `answer_usable_rate`: 0.8541666666666666
- `num_failures`: 7
- `failure_type_counts`: {'usable': 41, 'answer_quality_failure': 2, 'retrieval_document_failure': 2, 'citation_failure': 2, 'citation_and_answer_failure': 1}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.1 |
| gt-0017 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.95 |
| gt-0019 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.95 |
| gt-0022 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.3333333333333333 | 0.72 |
| gt-0037 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.18 |
| gt-0046 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.93 |
| gt-0049 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.74 |
