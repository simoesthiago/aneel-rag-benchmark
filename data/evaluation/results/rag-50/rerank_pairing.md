# Pareamento rerank vs baseline

> **Nota:** a config "rerank" reflete os defaults promovidos — pool 100 (F2) + filtro de revogadas (F1) + higiene de versões/submódulo exato (F1.5). Este pareamento mede **baseline cru vs pipeline completo**, não rerank isolado.

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 13 |
| `broken_by_rerank` | 5 |
| `stable_pass` | 22 |
| `stable_fail_same_type` | 5 |
| `stable_fail_changed_type` | 3 |

`answer_usable_rate`: baseline 0.562 -> rerank 0.729 (net_delta=+8)
`retrieval_document_failure`: baseline 6 -> rerank 1 (delta=-5)

## Salvas pelo rerank (13)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0014`: citation_and_answer_failure -> usable
- `gt-0023`: citation_failure -> usable
- `gt-0024`: citation_failure -> usable
- `gt-0025`: retrieval_passage_failure -> usable
- `gt-0026`: retrieval_document_failure -> usable
- `gt-0027`: retrieval_document_failure -> usable
- `gt-0028`: citation_and_answer_failure -> usable
- `gt-0029`: retrieval_document_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable
- `gt-0038`: citation_failure -> usable

## Quebradas pelo rerank (5)

- `gt-0001`: usable -> answer_quality_failure
- `gt-0009`: usable -> answer_quality_failure
- `gt-0035`: usable -> citation_failure
- `gt-0039`: usable -> citation_failure
- `gt-0046`: usable -> citation_and_answer_failure

## Falhas estáveis com tipo diferente (3)

- `gt-0002`: citation_and_answer_failure -> answer_quality_failure
- `gt-0030`: retrieval_document_failure -> citation_failure
- `gt-0049`: citation_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 13
- `broken`: 5
- `threshold` (2*broken): 10
- `delta_doc_failure`: -5
- `veredito`: **promote**
