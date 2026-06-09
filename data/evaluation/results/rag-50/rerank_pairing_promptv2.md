# Pareamento rerank vs baseline

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 6 |
| `broken_by_rerank` | 2 |
| `stable_pass` | 23 |
| `stable_fail_same_type` | 11 |
| `stable_fail_changed_type` | 6 |

`answer_usable_rate`: baseline 0.521 -> rerank 0.604 (net_delta=+4)
`retrieval_document_failure`: baseline 7 -> rerank 10 (delta=+3)

## Salvas pelo rerank (6)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0004`: citation_failure -> usable
- `gt-0008`: citation_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0018`: citation_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable

## Quebradas pelo rerank (2)

- `gt-0019`: usable -> answer_quality_failure
- `gt-0049`: usable -> retrieval_document_failure

## Falhas estáveis com tipo diferente (6)

- `gt-0013`: citation_and_answer_failure -> answer_quality_failure
- `gt-0017`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_failure -> citation_and_answer_failure
- `gt-0025`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0028`: answer_quality_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 6
- `broken`: 2
- `threshold` (2*broken): 4
- `delta_doc_failure`: +3
- `veredito`: **keep_optional**
- `razões`:
  - delta_doc_failure=+3 > +1
