# Finalistas RAG — comparativo (Marco C)

- Ground truth: retrieval-50-v2
- top_k: 10
- Gerador: gpt-5.4-mini | Juiz: gpt-5.4-mini
- `answer_usable = recall>0 AND citation>=0.5 AND correctness>=0.8`.
- Configs com rerank usam `rerank@100` + higiene (`sem_revogadas + sem_versoes_antigas + submodulo_exato`).
- Ordenado por `answer_usable_rate` (desc), desempate `ndcg_at_k`.
- Proveniência (runs):
  - `20260615T043417Z-97f94b5` (commit `97f94b5`)

| model                  | metodo_extracao   | rerank   |   answer_usable_rate |   citation_accuracy_avg |   answer_correctness_avg |   faithfulness_avg |   recall_at_k |   doc_recall_at_k |   ndcg_at_k |   latency_avg_ms |
|:-----------------------|:------------------|:---------|---------------------:|------------------------:|-------------------------:|-------------------:|--------------:|------------------:|------------:|-----------------:|
| text-embedding-3-large | texto             | True     |                0.812 |                   0.773 |                    0.922 |              0.976 |         0.958 |             0.958 |       0.872 |             4574 |
| text-embedding-3-large | markdown          | True     |                0.771 |                   0.723 |                    0.915 |              0.978 |         0.958 |             0.979 |       0.867 |             5186 |
| text-embedding-3-large | markdown          | False    |                0.604 |                   0.549 |                    0.862 |              0.957 |         0.812 |             0.875 |       0.636 |             2055 |
| text-embedding-3-large | texto             | False    |                0.562 |                   0.562 |                    0.838 |              0.931 |         0.792 |             0.875 |       0.627 |             1841 |
