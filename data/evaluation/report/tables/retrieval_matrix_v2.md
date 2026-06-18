# Matriz de retrieval — final v2 (pós-correção de chunking H12)

- Ground truth: retrieval-50-v2 | top_k: 10 | 48 perguntas avaliáveis (2 source_only fora do agregado).
- Filtros de higiene: `sem_revogadas + sem_versoes_antigas + submodulo_exato`.
- `fixed-size` vem do run v1 (não usa o splitter corrigido); estratégias estruturais vêm do run v2 (parser + splitter markdown-aware + merge).
- Ordenado por `doc_recall_at_k` (desc), desempate `ndcg_at_k`.
- Leitura dos líderes: no modelo large com rerank, `fixed-size·markdown` lidera
  `doc_recall` (0.979, nDCG 0.867) e `fixed-size·texto` lidera nDCG (0.872,
  doc_recall 0.958). Portanto a liderança é da família `fixed-size`, não de uma
  linha única que reúna todos os melhores valores.
- Proveniência:
  - v1 `20260614T161535Z-18d8e21` (commit `18d8e21`) — fixed-size.
  - v2 `20260616T033915Z-5e61c8f-dirty` (commit `5e61c8f`) — estruturais; stores em `simoesthiago/aneel-vectorstores-h12`.

| fonte                    | model                  | chunk_strategy     | metodo_extracao   | mode         | rerank   |   recall_at_k |   doc_recall_at_k |   precision_at_k |   mrr_at_k |   ndcg_at_k |   latency_avg_ms |
|:-------------------------|:-----------------------|:-------------------|:------------------|:-------------|:---------|--------------:|------------------:|-----------------:|-----------:|------------:|-----------------:|
| v1 (Marco B)             | text-embedding-3-large | fixed-size         | markdown          | flat         | True     |         0.958 |             0.979 |            0.196 |      0.875 |       0.867 |           5397.9 |
| v1 (Marco B)             | text-embedding-3-large | fixed-size         | texto             | flat         | True     |         0.958 |             0.958 |            0.21  |      0.898 |       0.872 |           6497.9 |
| v1 (Marco B)             | text-embedding-3-small | fixed-size         | markdown          | flat         | True     |         0.917 |             0.938 |            0.191 |      0.83  |       0.825 |           6469.4 |
| v1 (Marco B)             | text-embedding-3-large | fixed-size         | markdown          | flat         | False    |         0.896 |             0.938 |            0.177 |      0.724 |       0.748 |             14.6 |
| v1 (Marco B)             | text-embedding-3-large | fixed-size         | texto             | flat         | False    |         0.896 |             0.938 |            0.2   |      0.721 |       0.745 |             13.4 |
| v2 (parser+splitter H12) | text-embedding-3-large | article-aware      | markdown          | flat         | True     |         0.812 |             0.938 |            0.163 |      0.598 |       0.637 |            666.5 |
| v1 (Marco B)             | text-embedding-3-small | fixed-size         | texto             | flat         | True     |         0.896 |             0.917 |            0.194 |      0.845 |       0.827 |           6500.1 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | markdown          | hierarchical | True     |         0.833 |             0.917 |            0.163 |      0.62  |       0.662 |            679.1 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | markdown          | flat         | True     |         0.833 |             0.917 |            0.144 |      0.601 |       0.66  |            548.9 |
| v2 (parser+splitter H12) | text-embedding-3-small | article-aware      | markdown          | flat         | True     |         0.833 |             0.917 |            0.163 |      0.619 |       0.657 |            554.1 |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | markdown          | hierarchical | True     |         0.833 |             0.917 |            0.168 |      0.619 |       0.657 |            658.6 |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | texto             | hierarchical | True     |         0.792 |             0.917 |            0.162 |      0.605 |       0.635 |            666   |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | markdown          | flat         | True     |         0.812 |             0.896 |            0.143 |      0.61  |       0.659 |            513.7 |
| v2 (parser+splitter H12) | text-embedding-3-large | article-aware      | texto             | flat         | True     |         0.792 |             0.896 |            0.155 |      0.608 |       0.627 |            595.3 |
| v2 (parser+splitter H12) | text-embedding-3-large | article-aware      | markdown          | flat         | False    |         0.812 |             0.896 |            0.149 |      0.574 |       0.625 |            668.9 |
| v2 (parser+splitter H12) | text-embedding-3-small | article-aware      | texto             | flat         | True     |         0.75  |             0.896 |            0.148 |      0.603 |       0.623 |            527.4 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | texto             | flat         | True     |         0.771 |             0.896 |            0.135 |      0.585 |       0.613 |            486.2 |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | markdown          | hierarchical | False    |         0.833 |             0.896 |            0.144 |      0.54  |       0.602 |             20   |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | markdown          | flat         | False    |         0.771 |             0.896 |            0.126 |      0.481 |       0.545 |             19.6 |
| v1 (Marco B)             | text-embedding-3-small | fixed-size         | markdown          | flat         | False    |         0.833 |             0.875 |            0.17  |      0.615 |       0.63  |             12.6 |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | texto             | flat         | True     |         0.771 |             0.875 |            0.141 |      0.604 |       0.629 |            546.7 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | texto             | hierarchical | True     |         0.771 |             0.875 |            0.157 |      0.585 |       0.613 |            623.8 |
| v2 (parser+splitter H12) | text-embedding-3-large | article-aware      | texto             | flat         | False    |         0.729 |             0.875 |            0.136 |      0.524 |       0.576 |             17.5 |
| v2 (parser+splitter H12) | text-embedding-3-small | article-aware      | markdown          | flat         | False    |         0.708 |             0.875 |            0.123 |      0.47  |       0.517 |            501.6 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | markdown          | hierarchical | False    |         0.833 |             0.854 |            0.149 |      0.612 |       0.664 |             25.5 |
| v1 (Marco B)             | text-embedding-3-small | fixed-size         | texto             | flat         | False    |         0.833 |             0.854 |            0.189 |      0.621 |       0.643 |             13   |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | markdown          | flat         | False    |         0.792 |             0.854 |            0.135 |      0.568 |       0.606 |             24.9 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | texto             | hierarchical | False    |         0.75  |             0.833 |            0.155 |      0.553 |       0.588 |             24.9 |
| v2 (parser+splitter H12) | text-embedding-3-large | hierarchical-child | texto             | flat         | False    |         0.688 |             0.833 |            0.125 |      0.431 |       0.493 |             25.1 |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | texto             | hierarchical | False    |         0.646 |             0.812 |            0.129 |      0.408 |       0.45  |             20   |
| v2 (parser+splitter H12) | text-embedding-3-small | hierarchical-child | texto             | flat         | False    |         0.625 |             0.812 |            0.111 |      0.372 |       0.433 |             19.5 |
| v2 (parser+splitter H12) | text-embedding-3-small | article-aware      | texto             | flat         | False    |         0.583 |             0.771 |            0.112 |      0.301 |       0.365 |             14   |
