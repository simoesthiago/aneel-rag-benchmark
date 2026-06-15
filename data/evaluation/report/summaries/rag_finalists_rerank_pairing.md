# Efeito do rerank nos finalistas RAG (saved/broken por pergunta)

- Run: `20260615T043417Z-97f94b5` (commit `97f94b5`)
- Ground truth: retrieval-50-v2
- `saved` = não-usável sem rerank vira usável com rerank; `broken` = o contrário.

| extração | usável s/ rerank | usável c/ rerank | salvas | quebradas | net |
|---|---:|---:|---:|---:|---:|
| markdown | 29/48 | 37/48 | 11 | 3 | +8 |
| texto | 27/48 | 39/48 | 13 | 1 | +12 |

## markdown

- salvas pelo rerank: gt-0003, gt-0007, gt-0012, gt-0023, gt-0024, gt-0025, gt-0026, gt-0027, gt-0028, gt-0029, gt-0034
- quebradas pelo rerank: gt-0009, gt-0020, gt-0035

## texto

- salvas pelo rerank: gt-0007, gt-0010, gt-0012, gt-0014, gt-0020, gt-0023, gt-0024, gt-0025, gt-0026, gt-0027, gt-0028, gt-0029, gt-0030
- quebradas pelo rerank: gt-0039
