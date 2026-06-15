# Pareamento A/B RAG (Marco D)

- antes:  `data/evaluation/runs/rag/20260615T133052Z-ce9fed3` — usáveis 36/48, faithfulness 0.979
- depois: `data/evaluation/runs/rag/20260615T134946Z-ce9fed3-dirty` — usáveis 41/48, faithfulness 0.972
- regra: promover se `saved >= 2*broken` e faithfulness não cair além do ruído (tol. 0.01).

**saved=6 | broken=1 | net=+5 | veredito: PROMOTE**

- salvas: gt-0002, gt-0009, gt-0018, gt-0033, gt-0039, gt-0040
- quebradas: gt-0046
- estáveis usáveis: 35 | estáveis não-usáveis: 6
