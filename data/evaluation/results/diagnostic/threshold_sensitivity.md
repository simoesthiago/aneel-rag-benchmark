# Sensibilidade ao SUPPORT_EXCERPT_TOKEN_THRESHOLD

Config: text-embedding-3-large + fixed-size + markdown + flat (top-10, sem rerank)

Valor atual em produção: **0.60**.

|   threshold |   recall@10 |   n_failures | is_default   |
|------------:|------------:|-------------:|:-------------|
|        0.3  |      0.8542 |            7 | False        |
|        0.45 |      0.8333 |            8 | False        |
|        0.6  |      0.7708 |           11 | True         |
|        0.75 |      0.7292 |           13 | False        |
|        0.9  |      0.625  |           18 | False        |


## Casos sensíveis ao threshold

- Falham em 0.60 e passam em 0.30: ['gt-0005', 'gt-0017', 'gt-0025', 'gt-0034']
- Passam em 0.60 e falham em 0.90: ['gt-0004', 'gt-0015', 'gt-0019', 'gt-0020', 'gt-0021', 'gt-0022', 'gt-0028']
