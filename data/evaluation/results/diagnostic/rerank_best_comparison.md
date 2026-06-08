# Fase C — Rerank Cohere na melhor config

Config: text-embedding-3-large + fixed-size + markdown + flat

Perguntas avaliáveis: 48


## Métricas agregadas

| métrica | base | +rerank | delta |
|---|---:|---:|---:|
| passage_recall_at_k | 0.7708 | 0.7708 | +0.0000 |
| doc_recall_at_k | 0.8542 | 0.7917 | -0.0625 |
| mrr_at_k | 0.5833 | 0.6282 | +0.0448 |
| ndcg_at_k | 0.6243 | 0.6413 | +0.0169 |

## Por balde de falha

- **Balde 1 (doc não aparece):** falhas base: 2/2 (['gt-0002', 'gt-0027']); falhas rerank: 2/2 (['gt-0002', 'gt-0027'])
- **Balde 2 (doc aparece, trecho não):** falhas base: 4/4 (['gt-0005', 'gt-0017', 'gt-0025', 'gt-0034']); falhas rerank: 3/4 (['gt-0005', 'gt-0017', 'gt-0025'])
- **Balde 3 (trecho aparece, mas baixo):** falhas base: 5/5 (['gt-0007', 'gt-0012', 'gt-0026', 'gt-0029', 'gt-0030']); falhas rerank: 4/5 (['gt-0007', 'gt-0026', 'gt-0029', 'gt-0030'])

## Movimento de perguntas

- Salvos pelo rerank: ['gt-0012', 'gt-0034']
- Quebrados pelo rerank: ['gt-0028', 'gt-0049']
