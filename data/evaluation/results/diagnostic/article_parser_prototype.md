# Protótipo local do parser article-aware

Este relatório compara metadados publicados contra chunks gerados localmente com o parser atual da branch.

Recomendação: Protótipo reduz bem a fragmentação em texto, mas ainda reduz pouco em markdown, onde H12 era mais grave. Não recomendar re-embedding ainda; documentar e investigar limpeza/sectioning de markdown antes de rebuild oficial.

## Shape dos chunks

| strategy | método | kind | n pub | n proto | <30 pub | <30 proto | p50 pub | p50 proto |
|---|---|---|---:|---:|---:|---:|---:|---:|
| article-aware | markdown | chunks | 4242 | 3650 | 2483 | 2118 | 21 | 21 |
| article-aware | texto | chunks | 1508 | 997 | 465 | 160 | 50 | 90 |
| hierarchical-child | markdown | chunks | 4338 | 3807 | 2483 | 2118 | 22 | 23 |
| hierarchical-child | markdown | parents | 4242 | 3650 | 2483 | 2118 | 21 | 21 |
| hierarchical-child | texto | chunks | 1773 | 1311 | 465 | 160 | 64 | 130 |
| hierarchical-child | texto | parents | 1508 | 997 | 465 | 160 | 50 | 90 |

## Cobertura de support_excerpt

| strategy | método | kind | qid | doc | cov pub | cov proto | frag pub | frag proto |
|---|---|---|---|---|---:|---:|---|---|
| article-aware | markdown | chunks | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0022 | prodist-modulo-10 | 0.857 | 0.857 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | markdown | chunks | gt-0041 | proc-rede-8-3-pr | 0.389 | 0.389 | partido_em_3_chunks_adjacentes | partido_em_3_chunks_adjacentes |
| article-aware | texto | chunks | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0022 | prodist-modulo-10 | 0.929 | 0.929 | chunk_unico_cobre | chunk_unico_cobre |
| article-aware | texto | chunks | gt-0041 | proc-rede-8-3-pr | 0.974 | 0.974 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0022 | prodist-modulo-10 | 0.857 | 0.857 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | chunks | gt-0041 | proc-rede-8-3-pr | 0.389 | 0.389 | partido_em_3_chunks_adjacentes | partido_em_3_chunks_adjacentes |
| hierarchical-child | markdown | parents | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0022 | prodist-modulo-10 | 0.857 | 0.857 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | markdown | parents | gt-0041 | proc-rede-8-3-pr | 0.389 | 0.389 | partido_em_3_chunks_adjacentes | partido_em_3_chunks_adjacentes |
| hierarchical-child | texto | chunks | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0022 | prodist-modulo-10 | 0.857 | 0.857 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | chunks | gt-0041 | proc-rede-8-3-pr | 0.974 | 0.974 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0001 | ren-2021-1000 | 0.952 | 0.952 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0002 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0003 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0004 | ren-2021-1000 | 0.889 | 0.889 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0005 | ren-2021-1000 | 1.000 | 1.000 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0022 | prodist-modulo-10 | 0.929 | 0.929 | chunk_unico_cobre | chunk_unico_cobre |
| hierarchical-child | texto | parents | gt-0041 | proc-rede-8-3-pr | 0.974 | 0.974 | chunk_unico_cobre | chunk_unico_cobre |
