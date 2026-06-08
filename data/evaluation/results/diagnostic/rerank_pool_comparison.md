# Opção A — Rerank na melhor config: pool 50 vs pool 100

Config: text-embedding-3-large + fixed-size + markdown + flat

Perguntas: 48


## Métricas agregadas

| métrica | base | +rerank (pool 50) | +rerank (pool 100) | Δ pool100 vs base |
|---|---:|---:|---:|---:|
| passage_recall_at_k | 0.7708 | 0.7708 | 0.8125 | +0.0417 |
| doc_recall_at_k | 0.8542 | 0.7917 | 0.8333 | -0.0208 |
| mrr_at_k | 0.5833 | 0.6282 | 0.6516 | +0.0683 |
| ndcg_at_k | 0.6243 | 0.6413 | 0.6751 | +0.0508 |

## Movimento de perguntas

- **Pool 50 vs base**: salvos ['gt-0012', 'gt-0034']; quebrados ['gt-0028', 'gt-0049']
- **Pool 100 vs base**: salvos ['gt-0007', 'gt-0012', 'gt-0030', 'gt-0034']; quebrados ['gt-0028', 'gt-0049']
- **Pool 100 vs pool 50**: salvos a mais ['gt-0007', 'gt-0030']; perdidos a mais nenhum

## Por balde (pool 100 vs base)

- **Balde 1 (doc não aparece)**: base falha ['gt-0002', 'gt-0027']; rerank pool 100 falha ['gt-0002', 'gt-0027']
- **Balde 2 (doc aparece, trecho não)**: base falha ['gt-0005', 'gt-0017', 'gt-0025', 'gt-0034']; rerank pool 100 falha ['gt-0005', 'gt-0017', 'gt-0025']
- **Balde 3 (trecho aparece, mas baixo)**: base falha ['gt-0007', 'gt-0012', 'gt-0026', 'gt-0029', 'gt-0030']; rerank pool 100 falha ['gt-0026', 'gt-0029']
