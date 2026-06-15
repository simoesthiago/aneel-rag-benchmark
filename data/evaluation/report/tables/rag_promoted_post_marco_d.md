# Finalistas RAG — comparativo (Marco C)

- Ground truth: retrieval-50-v2
- top_k: 10
- Gerador: gpt-5.4-mini | Juiz: gpt-5.4-mini
- `answer_usable = recall>0 AND citation>=0.5 AND correctness>=0.8`.
- Configs com rerank usam `rerank@100` + higiene (`sem_revogadas + sem_versoes_antigas + submodulo_exato`).
- Ordenado por `answer_usable_rate` (desc), desempate `ndcg_at_k`.
- Proveniência (runs):
  - `20260615T140617Z-dd5f2c9` (commit `dd5f2c9`)

| model                  | metodo_extracao   | rerank   |   answer_usable_rate |   citation_accuracy_avg |   answer_correctness_avg |   faithfulness_avg |   recall_at_k |   doc_recall_at_k |   ndcg_at_k |   latency_avg_ms |
|:-----------------------|:------------------|:---------|---------------------:|------------------------:|-------------------------:|-------------------:|--------------:|------------------:|------------:|-----------------:|
| text-embedding-3-large | texto             | True     |                0.854 |                   0.837 |                    0.925 |              0.969 |         0.958 |             0.958 |       0.873 |             3145 |
| text-embedding-3-large | texto             | False    |                0.625 |                   0.642 |                    0.847 |              0.928 |         0.812 |             0.875 |       0.633 |             3684 |
