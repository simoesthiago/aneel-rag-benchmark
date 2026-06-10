# Pareamento do filtro de revogadas (Fase 1)

## rerank@100 sem filtro vs com filtro de revogadas

| Bucket | Count |
|---|---:|
| `saved_by_filter` | 2 |
| `broken_by_filter` | 1 |
| `stable_pass` | 27 |
| `stable_fail_same_type` | 15 |
| `stable_fail_changed_type` | 3 |

`answer_usable_rate`: before 0.583 -> after 0.604 (net_delta=+1)
`delta_doc_recall`: +0.021

### Salvas pelo filtro (2)

- `gt-0008`: citation_failure -> usable
- `gt-0030`: citation_failure -> usable

### Quebradas pelo filtro (1)

- `gt-0004`: usable -> citation_failure _[soft]_

### Falhas estáveis com tipo diferente (3)

- `gt-0017`: retrieval_document_failure -> retrieval_passage_failure
- `gt-0019`: citation_failure -> answer_quality_failure
- `gt-0022`: citation_and_answer_failure -> answer_quality_failure

### Veredito

Regra: promover filtro de revogadas SE delta_doc_recall >= -0.02 E hard_broken == 0 (soft breaks, com doc_recall intacto, não bloqueiam)

_hard break = regride E perde doc_recall (falha do filtro); soft break = regride mas mantém doc_recall (ruído de gerador)._

- saved: 2
- broken: 1 (hard=0, soft=1)
- delta_doc_recall: +0.021
- veredito: **promote**
