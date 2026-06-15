# Pareamento rerank vs baseline

> **Nota:** a config "rerank" reflete os defaults promovidos — pool 100 (F2) + filtro de revogadas (F1) + higiene de versões/submódulo exato (F1.5). Este pareamento mede **baseline cru vs pipeline completo**, não rerank isolado.

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_rerank` | 13 |
| `broken_by_rerank` | 2 |
| `stable_pass` | 28 |
| `stable_fail_same_type` | 1 |
| `stable_fail_changed_type` | 4 |

`answer_usable_rate`: baseline 0.625 -> rerank 0.854 (net_delta=+11)
`retrieval_document_failure`: baseline 6 -> rerank 2 (delta=-4)

## Salvas pelo rerank (13)

- `gt-0001`: answer_quality_failure -> usable
- `gt-0002`: citation_failure -> usable
- `gt-0005`: retrieval_passage_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable
- `gt-0010`: citation_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0023`: citation_and_answer_failure -> usable
- `gt-0025`: retrieval_document_failure -> usable
- `gt-0026`: retrieval_passage_failure -> usable
- `gt-0027`: retrieval_document_failure -> usable
- `gt-0028`: citation_failure -> usable
- `gt-0029`: retrieval_document_failure -> usable
- `gt-0030`: retrieval_document_failure -> usable

## Quebradas pelo rerank (2)

- `gt-0019`: usable -> citation_failure
- `gt-0037`: usable -> answer_quality_failure

## Falhas estáveis com tipo diferente (4)

- `gt-0017`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0022`: answer_quality_failure -> citation_and_answer_failure
- `gt-0046`: answer_quality_failure -> citation_failure
- `gt-0049`: citation_failure -> retrieval_document_failure

## Veredito

Regra: promover rerank a default SE saved_by_rerank >= 2 * broken_by_rerank E delta_doc_failure <= +1

- `saved`: 13
- `broken`: 2
- `threshold` (2*broken): 4
- `delta_doc_failure`: -4
- `veredito`: **promote**
