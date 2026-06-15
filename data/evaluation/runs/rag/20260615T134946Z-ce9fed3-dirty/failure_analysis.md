# Diagnóstico de usabilidade RAG

## Definição

`answer_usable = recall_at_k > 0 and citation_accuracy >= 0.5 and answer_correctness >= 0.8`.

Essa métrica separa resposta fiel ao contexto errado de resposta realmente útil para o usuário final.

## text-embedding-3-large|fixed-size|texto|flat+rerank

- `answer_usable_rate`: 0.8541666666666666
- `num_failures`: 7
- `failure_type_counts`: {'answer_quality_failure': 2, 'usable': 41, 'retrieval_document_failure': 2, 'citation_failure': 2, 'citation_and_answer_failure': 1}

| question_id | failure_type | next_focus | recall | doc_recall | citation | correctness |
|---|---|---|---:|---:|---:|---:|
| gt-0001 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 1.0 | 0.72 |
| gt-0015 | answer_quality_failure | prompt_generator_or_ground_truth | 1.0 | 1.0 | 0.5 | 0.12 |
| gt-0017 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 1.0 |
| gt-0019 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.93 |
| gt-0022 | citation_and_answer_failure | prompt_generator_or_context_use | 1.0 | 1.0 | 0.25 | 0.72 |
| gt-0046 | citation_failure | prompt_or_citation_selection | 1.0 | 1.0 | 0.3333333333333333 | 0.92 |
| gt-0049 | retrieval_document_failure | query_expansion_or_retrieval | 0.0 | 0.0 | 0.0 | 0.78 |
