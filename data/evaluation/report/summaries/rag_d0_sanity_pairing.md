# Pareamento A/B RAG (Marco D)

- antes:  `data/evaluation/runs/rag/20260615T133052Z-ce9fed3` — usáveis 36/48, faithfulness 0.979
- depois: `data/evaluation/runs/rag/20260615T134521Z-ce9fed3` — usáveis 37/48, faithfulness 0.975
- regra: promover se `saved >= 2*broken` e faithfulness não cair.

**saved=3 | broken=2 | net=+1 | veredito: KEEP**

- salvas: gt-0002, gt-0009, gt-0040
- quebradas: gt-0035, gt-0046
- estáveis usáveis: 34 | estáveis não-usáveis: 9
