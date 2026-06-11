# Pareamento rerank vs baseline

> **Nota:** a config "rerank" reflete os defaults promovidos — pool 100 (F2) + filtro de revogadas (F1). Este pareamento mede **baseline cru vs pipeline completo**, não rerank isolado.

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 9 |
| `broken_by_rerank` | 2 |
| `stable_pass` | 24 |
| `stable_fail_same_type` | 8 |
| `stable_fail_changed_type` | 5 |

`answer_usable_rate`: baseline 0.542 -> rerank 0.688 (net_delta=+7)
`retrieval_document_failure`: baseline 6 -> rerank 6 (delta=+0)

## Salvas pelo rerank (9)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0014`: citation_failure -> usable
- `gt-0030`: retrieval_document_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable
- `gt-0039`: citation_failure -> usable
- `gt-0040`: answer_quality_failure -> usable
- `gt-0046`: citation_failure -> usable

## Quebradas pelo rerank (2)

- `gt-0004`: usable -> citation_failure
- `gt-0037`: usable -> citation_and_answer_failure

## Falhas estáveis com tipo diferente (5)

- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0025`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0028`: citation_and_answer_failure -> retrieval_document_failure
- `gt-0049`: citation_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 9
- `broken`: 2
- `threshold` (2*broken): 4
- `delta_doc_failure`: +0
- `veredito`: **promote**
