# Pareamento query expansion vs baseline

## Par 1 — efeito de QE sobre baseline (sem rerank)

| Bucket | Count |
|---|---:|
| `saved_by_qe` | 4 |
| `broken_by_qe` | 6 |
| `stable_pass` | 20 |
| `stable_fail_same_type` | 13 |
| `stable_fail_changed_type` | 5 |

`answer_usable_rate`: before 0.542 -> after 0.500 (net_delta=-2)
`delta_retrieval_failures`: +2
`delta_doc_failure`: +1
`qe_status_counts` (na config com QE): {'ok': 48}

### Salvas pela QE (4)

- `gt-0003`: citation_and_answer_failure -> usable
- `gt-0013`: answer_quality_failure -> usable
- `gt-0023`: citation_and_answer_failure -> usable
- `gt-0034`: retrieval_passage_failure -> usable

### Quebradas pela QE (6)

- `gt-0004`: usable -> retrieval_passage_failure
- `gt-0010`: usable -> retrieval_document_failure
- `gt-0018`: usable -> citation_failure
- `gt-0037`: usable -> answer_quality_failure
- `gt-0039`: usable -> citation_failure
- `gt-0048`: usable -> citation_failure

### Falhas estáveis com tipo diferente (5)

- `gt-0019`: answer_quality_failure -> citation_and_answer_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0028`: citation_and_answer_failure -> citation_failure
- `gt-0040`: answer_quality_failure -> retrieval_passage_failure
- `gt-0046`: citation_failure -> citation_and_answer_failure

### Veredito

Regra: promover QE SE saved >= 2*broken E delta_retrieval_failures <= 0 E delta_doc_failure <= 0

- saved: 4
- broken: 6
- delta_retrieval_failures: +2
- delta_doc_failure: +1
- veredito: **keep_baseline**
- razões:
  - saved=4 < 2*broken=12
  - delta_retrieval_failures=+2 (piorou)
  - delta_doc_failure=+1 (piorou)

## Par 2 — efeito de QE sobre baseline+rerank

| Bucket | Count |
|---|---:|
| `saved_by_qe` | 3 |
| `broken_by_qe` | 5 |
| `stable_pass` | 22 |
| `stable_fail_same_type` | 14 |
| `stable_fail_changed_type` | 4 |

`answer_usable_rate`: before 0.562 -> after 0.521 (net_delta=-2)
`delta_retrieval_failures`: +2
`delta_doc_failure`: +0
`qe_status_counts` (na config com QE): {'ok': 48}

### Salvas pela QE (3)

- `gt-0001`: answer_quality_failure -> usable
- `gt-0013`: answer_quality_failure -> usable
- `gt-0039`: citation_failure -> usable

### Quebradas pela QE (5)

- `gt-0004`: usable -> citation_failure
- `gt-0012`: usable -> retrieval_document_failure
- `gt-0018`: usable -> citation_failure
- `gt-0036`: usable -> retrieval_passage_failure
- `gt-0040`: usable -> retrieval_passage_failure

### Falhas estáveis com tipo diferente (4)

- `gt-0022`: answer_quality_failure -> citation_and_answer_failure
- `gt-0023`: citation_and_answer_failure -> citation_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0026`: retrieval_document_failure -> citation_failure

### Veredito

Regra: promover QE SE saved >= 2*broken E delta_retrieval_failures <= 0 E delta_doc_failure <= 0

- saved: 3
- broken: 5
- delta_retrieval_failures: +2
- delta_doc_failure: +0
- veredito: **keep_baseline**
- razões:
  - saved=3 < 2*broken=10
  - delta_retrieval_failures=+2 (piorou)
