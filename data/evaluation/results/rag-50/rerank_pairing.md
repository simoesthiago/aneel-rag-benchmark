# Pareamento rerank vs baseline

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 6 |
| `broken_by_rerank` | 3 |
| `stable_pass` | 23 |
| `stable_fail_same_type` | 10 |
| `stable_fail_changed_type` | 6 |

`answer_usable_rate`: baseline 0.542 -> rerank 0.604 (net_delta=+3)
`retrieval_document_failure`: baseline 7 -> rerank 7 (delta=+0)

## Salvas pelo rerank (6)

- `gt-0003`: citation_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0030`: retrieval_document_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable
- `gt-0046`: citation_failure -> usable

## Quebradas pelo rerank (3)

- `gt-0001`: usable -> answer_quality_failure
- `gt-0004`: usable -> citation_failure
- `gt-0037`: usable -> citation_and_answer_failure

## Falhas estáveis com tipo diferente (6)

- `gt-0013`: citation_and_answer_failure -> answer_quality_failure
- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0025`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0028`: citation_failure -> retrieval_document_failure
- `gt-0049`: answer_quality_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 6
- `broken`: 3
- `threshold` (2*broken): 6
- `delta_doc_failure`: +0
- `veredito`: **promote**
