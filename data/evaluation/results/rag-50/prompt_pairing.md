# Pareamento prompt v2 vs prompt v1 (config baseline, sem rerank)

## Resumo

| Bucket | Count |
|---|---:|
| `saved_by_prompt_v2` | 4 |
| `broken_by_prompt_v2` | 3 |
| `stable_pass` | 21 |
| `stable_fail_same_type` | 17 |
| `stable_fail_changed_type` | 3 |

`answer_usable_rate`: v1 0.500 -> v2 0.521 (net_delta=+1)
`citation_failures`: delta=-2
`answer_failures`: delta=-2

## Salvas pelo prompt v2 (4)

- `gt-0019`: citation_failure -> usable
- `gt-0039`: citation_failure -> usable
- `gt-0046`: citation_failure -> usable
- `gt-0049`: answer_quality_failure -> usable

## Quebradas pelo prompt v2 (3)

- `gt-0004`: usable -> citation_failure
- `gt-0008`: usable -> citation_failure
- `gt-0018`: usable -> citation_failure

## Falhas estáveis com tipo diferente (3)

- `gt-0022`: citation_and_answer_failure -> answer_quality_failure
- `gt-0024`: citation_and_answer_failure -> citation_failure
- `gt-0028`: citation_and_answer_failure -> answer_quality_failure

## Veredito

Regra: promover prompt v2 SE saved >= 2*broken E delta_citation_failures <= 0 E delta_answer_failures <= 0

- saved: 4
- broken: 3
- delta_citation_failures: -2
- delta_answer_failures: -2
- veredito: **keep_v1**
- razões:
  - saved=4 < 2*broken=6
