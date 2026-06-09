# Pareamento rerank vs baseline

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 4 |
| `broken_by_rerank` | 0 |
| `stable_pass` | 24 |
| `stable_fail_same_type` | 13 |
| `stable_fail_changed_type` | 7 |

`answer_usable_rate`: baseline 0.500 -> rerank 0.583 (net_delta=+4)
`retrieval_document_failure`: baseline 7 -> rerank 10 (delta=+3)

## Salvas pelo rerank (4)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable
- `gt-0046`: citation_failure -> usable

## Quebradas pelo rerank (0)

_Nenhuma pergunta neste bucket._

## Falhas estáveis com tipo diferente (7)

- `gt-0013`: citation_and_answer_failure -> answer_quality_failure
- `gt-0017`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0019`: citation_failure -> citation_and_answer_failure
- `gt-0022`: citation_and_answer_failure -> answer_quality_failure
- `gt-0025`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0028`: citation_and_answer_failure -> retrieval_document_failure
- `gt-0049`: answer_quality_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 4
- `broken`: 0
- `threshold` (2*broken): 0
- `delta_doc_failure`: +3
- `veredito`: **keep_optional**
- `razões`:
  - delta_doc_failure=+3 > +1
