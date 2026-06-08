# 1.3-alt-b — Concept-dense persiste em outras configs?

Teste das 3 perguntas com Achado 7 (gt-0005, gt-0025, gt-0027) em 6 configs Dense+Hierarchical já publicadas. Sem rerank, sem query expansion.

Top-100 recuperados; passage/doc recall medidos em top-10. Matching threshold = 0.6.


## Caveat sobre gt-0027

A oracle_expansion de 1.3-alt para gt-0027 NÃO incluiu os termos discriminantes do excerpt (`taxa regulatória de remuneração de capital`, `estrutura de capital regulatória`). Portanto, a classificação de gt-0027 como concept-dense ainda depende de teste com oracle de verdade. Este teste cross-config ajuda mas não fecha a questão para gt-0027.


---

## gt-0005

**Pergunta:** Em geração distribuída, quando uma usina fotovoltaica com armazenamento pode ser considerada central geradora de fonte despachável pela REN 1000/2021?
**Doc esperado:** `ren-2021-1000`
**Support excerpt:** > central geradora de fonte despachável: ... geração fotovoltaica de até 3 MW de potência instalada, que apresentem capacidade de modulação de geração por meio do armazenamento de energia em baterias, em quantidade de, pelo menos, 20% da capacidade de geração mensal da central geradora.

| config | passage_recall@10 | doc_recall@10 | chunk_doc rank | match rank | best cov rank | best cov |
|---|---:|---:|---:|---:|---:|---:|
| fixed/md/flat | 0.0 | 1.0 | 1 | None | 1 | 0.5 |
| fixed/tx/flat | 0.0 | 1.0 | 3 | None | 54 | 0.591 |
| article/tx/flat | 0.0 | 1.0 | 1 | 12 | 67 | 1.0 |
| hier/tx/hier | 1.0 | 1.0 | 1 | 1 | 1 | 1.0 |
| article/md/flat | 0.0 | 1.0 | 2 | 12 | 67 | 1.0 |
| hier/md/hier | 1.0 | 1.0 | 1 | 1 | 1 | 1.0 |

---

## gt-0025

**Pergunta:** No PRORET Submódulo 2.3, quando imóveis sem título definitivo podem ser considerados na base de ativos?
**Doc esperado:** `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003`
**Support excerpt:** > Os imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária podem ser incluídos na base de remuneração, desde que se enquadrem nas seguintes condições: a) ser um imóvel elegível (imóvel operacional); b) encontrar-se registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) existir comprovação de que a documentação de titularidade de propriedade encontra-se em processo de regularização (protocolo em cartório ou similar).

| config | passage_recall@10 | doc_recall@10 | chunk_doc rank | match rank | best cov rank | best cov |
|---|---:|---:|---:|---:|---:|---:|
| fixed/md/flat | 0.0 | 1.0 | 3 | None | 3 | 0.474 |
| fixed/tx/flat | 0.0 | 0.0 | 33 | None | 57 | 0.132 |
| article/tx/flat | 0.0 | 0.0 | 46 | None | 46 | 0.184 |
| hier/tx/hier | 0.0 | 0.0 | 54 | None | 94 | 0.5 |
| article/md/flat | 0.0 | 0.0 | 23 | None | 23 | 0.132 |
| hier/md/hier | 0.0 | 0.0 | 36 | None | 36 | 0.289 |

---

## gt-0027

**Pergunta:** Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras?
**Doc esperado:** `proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003`
**Support excerpt:** > Estabelecer metodologia para definição da taxa regulatória de remuneração de capital e estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.

| config | passage_recall@10 | doc_recall@10 | chunk_doc rank | match rank | best cov rank | best cov |
|---|---:|---:|---:|---:|---:|---:|
| fixed/md/flat | 0.0 | 0.0 | None | None | None | 0.0 |
| fixed/tx/flat | 0.0 | 0.0 | None | None | None | 0.0 |
| article/tx/flat | 0.0 | 0.0 | 25 | None | 25 | 0.312 |
| hier/tx/hier | 0.0 | 0.0 | 40 | None | 40 | 0.312 |
| article/md/flat | 0.0 | 1.0 | 4 | 40 | 40 | 0.75 |
| hier/md/hier | 0.0 | 1.0 | 4 | 42 | 42 | 0.75 |

---

## Visão cruzada — passage_recall@10

| config | gt-0005 | gt-0025 | gt-0027 |
|---|---:|---:|---:|
| fixed/md/flat | 0.0 | 0.0 | 0.0 |
| fixed/tx/flat | 0.0 | 0.0 | 0.0 |
| article/tx/flat | 0.0 | 0.0 | 0.0 |
| hier/tx/hier | 1.0 | 0.0 | 0.0 |
| article/md/flat | 0.0 | 0.0 | 0.0 |
| hier/md/hier | 1.0 | 0.0 | 0.0 |

## Visão cruzada — best cov no top-100

| config | gt-0005 | gt-0025 | gt-0027 |
|---|---:|---:|---:|
| fixed/md/flat | 0.5 | 0.474 | 0.0 |
| fixed/tx/flat | 0.591 | 0.132 | 0.0 |
| article/tx/flat | 1.0 | 0.184 | 0.312 |
| hier/tx/hier | 1.0 | 0.5 | 0.312 |
| article/md/flat | 1.0 | 0.132 | 0.75 |
| hier/md/hier | 1.0 | 0.289 | 0.75 |
