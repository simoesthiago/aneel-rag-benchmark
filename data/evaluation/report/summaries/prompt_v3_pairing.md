# Pareamento A/B RAG (Marco D)

- antes:  `/tmp/aneel_prompt_default` — usáveis 38/48, faithfulness 0.964
- depois: `/tmp/aneel_prompt_v3` — usáveis 39/48, faithfulness 0.987
- regra: promover se `saved >= 2*broken` e faithfulness não cair além do ruído (tol. 0.01).
- nota: os diretórios `/tmp` foram usados para evitar versionar novos runs brutos;
  este arquivo preserva o resumo agregado do gate.

**saved=4 | broken=3 | net=+1 | veredito: KEEP**

- salvas: gt-0001, gt-0005, gt-0018, gt-0037
- quebradas: gt-0019, gt-0028, gt-0029
- estáveis usáveis: 35 | estáveis não-usáveis: 6
