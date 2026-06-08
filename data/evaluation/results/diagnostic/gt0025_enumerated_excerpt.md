# gt-0025 — diagnóstico de excerpt enumerado

Verifica se as 4 condições (a, b, c, d) do support_excerpt aparecem juntas ou partidas entre chunks, por estratégia de chunking.

**Pergunta:** No PRORET Submódulo 2.3, quando imóveis sem título definitivo podem ser considerados na base de ativos?
**Doc esperado:** `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003`
**Support excerpt:** > Os imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária podem ser incluídos na base de remuneração, desde que se enquadrem nas seguintes condições: a) ser um imóvel elegível (imóvel operacional); b) encontrar-se registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) existir comprovação de que a documentação de titularidade de propriedade encontra-se em processo de regularização (protocolo em cartório ou similar).

**Âncoras procuradas:**
- (a) `imóvel elegível`
- (b) `registrado na contabilidade`
- (c) `documentação que comprove a aquisição`
- (d) `processo de regularização`

## Resultados por config

| config | n_chunks doc | a (chunks) | b | c | d | best_cov_overall | best_cov_top10 | **categoria** |
|---|---:|---|---|---|---|---:|---:|---|
| fixed/md/flat | 43 | 3 | 3,5,16,17 | 3 | 3,30,31 | 1.0 | 0.474 | **`matching_exigente_demais`** |
| fixed/tx/flat | 59 | 3 | 3,5,17 | 3 | 3,31 | 1.0 | 0.0 | **`excerpt_longo_em_um_chunk_mas_mal_ranqueado`** |
| article/md/flat | 19 | — | 2 | — | 11 | 0.5 | 0.0 | **`excerpt_partido_entre_chunks`** |
| article/tx/flat | 29 | — | 2 | — | 11 | 0.5 | 0.0 | **`excerpt_partido_entre_chunks`** |
| hier/md/hier | 19 | — | 2 | — | 11 | 0.5 | 0.0 | **`excerpt_partido_entre_chunks`** |
| hier/tx/hier | 29 | — | 2 | — | 11 | 0.5 | 0.0 | **`excerpt_partido_entre_chunks`** |

## Justificativas

- **fixed/md/flat** → `matching_exigente_demais`
  - As 4 condições estão num único chunk (índice [3]). Esse chunk está no top-10 mas cov=0.47 < 0.6. Excerpt é tão longo que mesmo presença completa não dá cobertura de tokens informativos suficiente.
- **fixed/tx/flat** → `excerpt_longo_em_um_chunk_mas_mal_ranqueado`
  - As 4 condições estão num chunk único (índice [3]), mas esse chunk não está no top-10. Retrieval não o priorizou.
- **article/md/flat** → `excerpt_partido_entre_chunks`
  - Condições aparecem em chunks distintos: {'a': [], 'b': [2], 'c': [], 'd': [11]}. Chunking partiu o excerpt.
- **article/tx/flat** → `excerpt_partido_entre_chunks`
  - Condições aparecem em chunks distintos: {'a': [], 'b': [2], 'c': [], 'd': [11]}. Chunking partiu o excerpt.
- **hier/md/hier** → `excerpt_partido_entre_chunks`
  - Condições aparecem em chunks distintos: {'a': [], 'b': [2], 'c': [], 'd': [11]}. Chunking partiu o excerpt.
- **hier/tx/hier** → `excerpt_partido_entre_chunks`
  - Condições aparecem em chunks distintos: {'a': [], 'b': [2], 'c': [], 'd': [11]}. Chunking partiu o excerpt.
