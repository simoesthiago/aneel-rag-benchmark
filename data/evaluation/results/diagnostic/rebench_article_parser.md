# Rebench escopado — parser article-aware corrigido (H12)

- provider: `openai` | modelo: `text-embedding-3-large` | método: `texto`
- ground truth: `retrieval-50-v2` | top_k: 10 | amostra: None
- alvo (fixed-size): recall 0.896 / doc_recall 0.938
- régua de promoção: article-aware recall >= 0.8

**Veredito: NÃO PROMOVER: article-aware·texto recall 0.680 < 0.8 — o fix não fecha a lacuna. Documentar que fixed-size venceu por robustez; sem re-embedding oficial.**

| strategy | mode | recall antes | recall depois | Δ recall | doc_recall antes | doc_recall depois | nDCG antes | nDCG depois |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| article-aware | flat | 0.625 | 0.680 | +0.055 | 0.833 | 0.800 | 0.465 | 0.524 |
| hierarchical-child | flat | 0.542 | 0.620 | +0.078 | 0.812 | 0.820 | 0.401 | 0.451 |
| hierarchical-child | hierarchical | 0.583 | 0.700 | +0.117 | 0.812 | 0.820 | 0.459 | 0.537 |
