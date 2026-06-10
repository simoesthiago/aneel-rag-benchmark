# Pareamento de pool de rerank (Fase 2)

## Par 1 — DECISÃO — rerank@50 vs rerank@100

| Bucket | Count |
|---|---:|
| `saved_by_pool100` | 2 |
| `broken_by_pool100` | 1 |
| `stable_pass` | 27 |
| `stable_fail_same_type` | 14 |
| `stable_fail_changed_type` | 4 |

`answer_usable_rate`: before 0.583 -> after 0.604 (net_delta=+1)
`delta_doc_recall`: +0.042

### Salvas pelo pool maior (2)

- `gt-0001`: answer_quality_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable

### Quebradas pelo pool maior (1)

- `gt-0047`: usable -> answer_quality_failure

### Falhas estáveis com tipo diferente (4)

- `gt-0019`: citation_and_answer_failure -> citation_failure
- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0030`: retrieval_document_failure -> citation_failure

### Veredito (decisivo)

Regra: promover pool 100 SE saved >= 2*broken E delta_doc_recall >= -0.02

- saved: 2
- broken: 1
- delta_doc_recall: +0.042
- veredito: **promote**

## Par 2 — CONTEXTO — baseline vs rerank@100

| Bucket | Count |
|---|---:|
| `saved_by_pool100` | 6 |
| `broken_by_pool100` | 2 |
| `stable_pass` | 23 |
| `stable_fail_same_type` | 9 |
| `stable_fail_changed_type` | 8 |

`answer_usable_rate`: before 0.521 -> after 0.604 (net_delta=+4)
`delta_doc_recall`: -0.021

### Salvas pelo pool maior (6)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0007`: retrieval_document_failure -> usable
- `gt-0012`: retrieval_document_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable
- `gt-0039`: citation_failure -> usable
- `gt-0046`: citation_failure -> usable

### Quebradas pelo pool maior (2)

- `gt-0028`: usable -> retrieval_document_failure
- `gt-0047`: usable -> answer_quality_failure

### Falhas estáveis com tipo diferente (8)

- `gt-0013`: citation_and_answer_failure -> answer_quality_failure
- `gt-0017`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0019`: answer_quality_failure -> citation_failure
- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0025`: retrieval_passage_failure -> retrieval_document_failure
- `gt-0030`: retrieval_document_failure -> citation_failure
- `gt-0049`: answer_quality_failure -> retrieval_document_failure

### Veredito (informativo)

Regra: promover pool 100 SE saved >= 2*broken E delta_doc_recall >= -0.02

- saved: 6
- broken: 2
- delta_doc_recall: -0.021
- veredito: **keep_pool50**
- razões:
  - delta_doc_recall=-0.021 < -0.02
