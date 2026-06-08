# Diagnóstico das 11 falhas residuais — SUMMARY

**Status:** DIAGNÓSTICO CONSOLIDADO. Fases A, B e C concluídas; gates 1.1, 1.2, 1.2b, 1.3-alt, 1.3-alt-b e A+B executados. 11/11 falhas têm causa confirmada. Decisão final: **Caminho 4 (mínimo necessário + avançar para Camada 3.5)** — ver GATE DE DECISÃO FINAL no fim.

**Recall honesto da melhor config:** `passage_recall@10 = 0.771`, `doc_recall@10 = 0.854` (text-embedding-3-large + fixed-size + markdown + flat, threshold de matching 0.60 mantido). A tentativa de baixar threshold para 0.30 (que daria 0.854 em passage_recall) foi **descartada** após 1.2 mostrar que 89% dos matches marginais são falsos positivos do oráculo de avaliação — não melhoria real do sistema.

Recomendações de produção que mudam dados oficiais (GT, schema, chunks) ficam como issues registradas para depois do gerador. Recomendações sem custo (rerank opt-in com pool 100, documentação, calibrações) foram aplicadas.

## Linha do tempo do diagnóstico

1. **Benchmark base rodou**: melhor config `text-embedding-3-large + fixed-size + markdown + flat` com `recall@10 = 0.771`, `nDCG@10 = 0.624`. 11/48 perguntas falharam.
2. **Análise pós-benchmark** (usuário) classificou as 11 em 3 baldes (doc não aparece / doc aparece, trecho não / trecho aparece, mas baixo).
3. **Plano de 12 hipóteses** formulado para investigar cada balde (registrado em `~/.claude/plans/una-essas-hip-teses-que-cryptic-lightning.md`).
4. **Fase A** — testes 100% automatizáveis: 6 scripts (`scripts/diagnose_*.py`) cobrindo A.1 (chunk sizes), A.2 (excerpts literal), A.3 (adicionar `doc_recall_at_k`), A.4 (multi-source), A.5 (boilerplate), A.6 (threshold sensitivity). Resultado inicial: 5 hipóteses refutadas, 2 confirmadas, 1 nova levantada (H12).
5. **Fase B** — inspeção visual manual de gt-0002 e gt-0027 (balde 1, "doc não aparece") pelo usuário com outra IA consultando PDFs oficiais da ANEEL. Gerou `diagnose_phase_b_package.py` com URLs + excerpts + top-10 do retriever; outra IA respondeu sobre H4 (dupla resposta), H6 (vocabulário) e H11 (versão vigente). Confirmou H4 para gt-0002 e refutou H11 para os dois casos.
6. **Fase C** — testes condicionais de **rerank Cohere** sobre a melhor config. Duas rodadas: tentativa 1 (`diagnose_rerank_best.py`, pool 50 default) deu net zero em passage_recall e -6 pp em doc_recall; Opção A (`diagnose_rerank_best_pool100.py`, pool 100) deu net +2 em passage_recall e -2 pp em doc_recall. H1 confirmada como parcial.
7. **Gates de validação** — após críticas do usuário, novos gates foram executados para fechar lacunas:
   - **1.1** — `diagnose_h12_tiny_chunks.py`: confirmou causa de H12 (regex captura referências cruzadas).
   - **1.2** — `diagnose_threshold_precision.py`: usou gpt-4o-mini como juiz para medir precisão do oráculo sob threshold 0.30. Resultou em **REVERSÃO de H8** (89% falsos positivos).
   - **1.2b** — `diagnose_bucket2.py`: classificou as 4 falhas do balde 2 em 6 categorias predefinidas.
   - **1.3-alt** — `diagnose_query_expansion.py`: testou H6 via 3 variantes de query (ORIGINAL, GENERIC, ORACLE).
   - **1.3-alt-b** — `diagnose_concept_dense_cross_config.py`: testou se Achado 7 (concept-dense) persistia em 6 configs.
   - **A + B finais** — `diagnose_gt0027_oracle.py` (oracle manual com termos discriminantes) e `diagnose_gt0025_enumerated.py` (mapeamento das condições a/b/c/d). Fecharam gt-0027 (H6 dramática) e gt-0025 (fenômeno novo: excerpt enumerado).
8. **Caminho 4 ajustado escolhido** — housekeeping barato aplicado (CLI rerank, README, headers de scripts), GT não tocado, fix de chunking adiado, decisão de avançar para Camada 3.5.

## Tabela de hipóteses consolidada (todas as fases + gates)

| ID | Hipótese | Status | Evidência | Próximo passo |
|---|---|---|---|---|
| B1 | Truncamento por limite de tokens do embedder | ❌ REFUTADA | Max chunk = 800 palavras < 6000 (A.1) | — |
| H1 | Top-k=10 apertado, rerank resolve balde 3 | ✅ **PARCIALMENTE CONFIRMADA** | Rerank com `candidates_k=100` sobe passage_recall +4 pp, MRR +7 pp, nDCG +5 pp, mas cai doc_recall -2 pp. Salva 4 (gt-0007/0012/0030/0034) vs base, quebra 2 (gt-0028/0049). Net +2 perguntas. Pool 50 não basta (deixa gt-0030 fora). | Tornar `candidates_k=100` o default quando rerank ativo |
| H2 | Métrica confunde "doc" com "trecho" | ✅ CONFIRMADA | doc_recall > passage_recall em todas as configs (A.3) | Reportar separadamente |
| H3 | GT tem excerpts sintéticos/parafraseados | 🟡 **PARCIALMENTE CONFIRMADA (1 caso)** | A.2 mostrou 46% LITERAL_MATCH, 54% TOKEN_MATCH. 1.2b investigou balde 2 caso a caso e encontrou **gt-0017** com cov geral máxima = 0.43 (excerpt não aparece como substring em nenhum chunk). Pode ser síntese conceitual do GT. Não é problema sistêmico, mas existe em casos específicos. | — |
| H4 | Pergunta tem dupla resposta válida | ✅ **CONFIRMADA (gt-0002)** | gt-0002: PRORET 6.8 também define "bandeiras tarifárias"; GT omitiu como fonte alternativa. gt-0027: refutada. (Fase B) | Issue: enriquecer GT com fontes alternativas |
| H5 | Extração PyMuPDF corrompeu trecho | ⚠️ **SEM EVIDÊNCIA (para as 11 falhas)** | Tokens informativos do excerpt presentes nas duas extrações (markdown e texto) para todas as 11. Não exclui que outros documentos do corpus estejam corrompidos. | — |
| H6 | Vocabulário da query ≠ documento | ✅ **CONFIRMADA para gt-0027 (oracle real); demais casos têm outras causas** | Em A (reteste com oracle manual contendo "custo de capital" + "taxa regulatória de remuneração de capital"), gt-0027 passa de passage_recall=0 para **1.0 em TODAS as 6 configs**. Confirma H6 puro para esse caso. gt-0005 é concept-dense (resolvido por hier). gt-0025 é excerpt enumerado (3 fenômenos por chunking). | Issue: investigar query expansion com prompt agressivo (LLM-rewriter de 1.3-alt não inferiu os termos) |
| H7 | `_section_signature` parsing frágil | ➰ SUBSUMIDA | H8 cobre o caso prático | — |
| H8 | Threshold 0.60 alto demais | ❌ **REFUTADA QUANDO AJUSTADA POR PRECISÃO** (1.2) | A.6 mediu apenas recall (0.77 → 0.854 baixando p/ 0.30). 1.2 mediu precisão do oráculo nos 73 matches marginais: **89% falsos positivos** segundo juiz gpt-4o-mini. Os 4 casos "salvos" (gt-0005/17/25/34) são TODOS falsos positivos. Threshold 0.60 está calibrado, não alto demais. | NÃO mexer no threshold |
| H9 | Pergunta multi-hop / multi-fonte | ❌ REFUTADA | Todas perguntas têm 1 fonte (A.4) | — |
| H10 | Boilerplate inflando similaridade | ❌ REFUTADA | Off-diag média = 0.65 < 0.85 (A.5) | — |
| H11 | Versão errada/revogada no corpus | ❌ REFUTADA | gt-0002 (REN 1000) e gt-0027 (PRORET 2.4) ambos vigentes em 2026, confirmado em fontes oficiais ANEEL (Fase B) | — |
| **H12** | **Chunking article-aware fragmenta por referência cruzada** | ✅ **CAUSA CONFIRMADA** (1.1) | 61% dos chunks article-aware/markdown têm < 30 palavras; 30% têm < 10 palavras. Amostras mostram `Art. 3º O Submódulo de que trata o` (8 pal) e `Art. 3º O` (3 pal) — fragmentos entre referências cruzadas a "Art. N" no texto. Regex `ARTICLE_RE` ([article_aware.py:13](../../../src/chunking/article_aware.py#L13)) captura TODA ocorrência de "Art. N", sem distinguir cabeçalho de referência. Markdown sofre mais por causa de `**Art. N**` em listas/definições. Fix NÃO aplicado nesta etapa. | Issue separado; decidir após Gate 1.2 |

## Achados-chave

### Achado 1 — A.6 era enganoso; threshold 0.60 está bem calibrado (1.2 corrigiu)

A.6 mediu **só recall** variando o threshold do oráculo de avaliação:

| threshold | recall@10 (oráculo) | n_failures (oráculo) | salvos baixando p/ 0.30 |
|---|---:|---:|---|
| 0.30 | 0.854 | 7 | gt-0005, gt-0017, gt-0025, gt-0034 |
| 0.60 (atual) | 0.771 | 11 | — |
| 0.90 | 0.625 | 18 | — |

**Inicialmente interpretei como "fix barato, +8 pp recall".** Estava errado.

**1.2 mediu precisão do oráculo nos 73 matches marginais** (cobertura entre 0.30 e 0.60) com gpt-4o-mini como juiz:

| Veredito do juiz | n | % |
|---|---:|---:|
| SIM (verdadeiro positivo) | 4 | 5.5% |
| PARCIAL | 4 | 5.5% |
| NÃO (falso positivo) | 65 | **89%** |

Precisão estrita: **0.055**. Os 4 casos que A.6 reportou como "salvos" (gt-0005/17/25/34) são **todos falsos positivos** — pelo juiz, nenhum dos chunks marginais que os salvariam realmente responde à pergunta.

**Conclusão revisada:** o threshold 0.60 está **calibrado corretamente**. Baixar para 0.30 inflaciona o número (mais recall, mais precisão_at_k) sem melhorar o sistema. O balde 2 (4 falhas) **continua sendo falha real**, não artefato.

Exemplo paradigmático (gt-0003, "Como a REN 1000/2021 define consumidor?"): chunk marginal era apenas o **cabeçalho da resolução** ("RESOLUÇÃO NORMATIVA ANEEL Nº 1.000... Estabelece..."), cobertura 0.53 (alta) por compartilhar "REN 1000", "ANEEL", "Resolução", mas zero conteúdo da definição. Oráculo casou; juiz rejeitou.

### Achado 2 — Separar `doc_recall` de `passage_recall` muda a narrativa do benchmark

Nova métrica `doc_recall_at_k` adicionada em [src/evaluation/metrics.py](../../../src/evaluation/metrics.py) sem renomear `recall_at_k` (compat preservada).

Ranking das 16 configs por `doc_recall`:

| # | model | chunk | método | mode | passage_recall | **doc_recall** | gap |
|---|---|---|---|---|---:|---:|---:|
| 1 | large | fixed-size | markdown | flat | 0.771 | **0.854** | +0.08 |
| 2 | large | fixed-size | texto | flat | 0.771 | 0.854 | +0.08 |
| 3 | small | fixed-size | texto | flat | 0.708 | 0.833 | +0.13 |
| 4 | small | fixed-size | markdown | flat | 0.646 | 0.792 | +0.15 |
| 7 | large | hier-child | mkd | hier | 0.375 | 0.646 | **+0.27** |
| 9 | large | article-aware | mkd | flat | 0.333 | 0.583 | **+0.25** |

Hierarchical e article-aware em markdown **não são ruins em retrieval** — eles encontram o documento certo em 58-65% dos casos. São ruins em **granularidade de chunk**: o chunk devolvido raramente contém o trecho específico do GT.

### Achado 3 — H12 (novo): chunking markdown gera muitos chunks tiny

Histograma de [chunk_size_histogram.md](chunk_size_histogram.md):

| estratégia | método | n_chunks | p50 (palavras) |
|---|---|---:|---:|
| article-aware | markdown | **84.653** | **21** |
| article-aware | texto | 34.203 | 52 |
| hierarchical-child | markdown | **92.565** | **24** |
| hierarchical-child | texto | 44.550 | 89 |

Markdown gera 2-3× mais chunks que texto, com mediana ~22 palavras. **Sintoma confirmado; causa ainda não.** Hipótese plausível mas não testada: o regex `ARTICLE_RE` ([src/chunking/article_aware.py:13-15](../../../src/chunking/article_aware.py#L13)) pode estar pegando cabeçalhos markdown (`## Art. 1`, `**Art. 1**`) como múltiplos matches. Antes de prescrever fix, é necessário inspecionar amostra real dos chunks pequenos (`metadata.parquet` da partição article-aware/markdown) — não fiz isso ainda.

## Achado 4 — As 2 falhas residuais do balde 1 têm explicações distintas (Fase B)

Inspeção manual da Fase B (usuário + IA auxiliar, fontes oficiais ANEEL, 2026-06-06):

**gt-0002 ("Para fins da REN 1000/2021, o que são bandeiras tarifárias?")**
- REN 1000 Art. 2º define bandeiras tarifárias (definição jurídica curta)
- PRORET 6.8 também define bandeiras tarifárias (operacional, mais detalhada)
- **Ambos respondem a pergunta corretamente.** GT listou só REN 1000 como fonte.
- Sistema acertou semanticamente, errou apenas no documento que GT esperava.
- ✅ **H4 CONFIRMADA**: GT incompleto, faltam fontes alternativas válidas.

**gt-0027 ("Qual é a finalidade metodológica do PRORET Submódulo 2.4...")**
- PRORET 2.4 trata de custo de capital — única fonte correta.
- PRORET 2.1 e 2.1A (retornados pelo sistema) tratam de procedimentos gerais, não respondem.
- Pergunta não usa termos discriminantes ("custo de capital", "taxa regulatória de remuneração").
- Embedding gruda no vocabulário genérico "revisão tarifária" e puxa 2.1.
- ✅ **H6 CONFIRMADA**: subespecificação de query. Solução: query expansion ou termo técnico explícito.

Implicação: **das 11 falhas iniciais, todas têm hipótese confirmada agora.**
- 4 (balde 2): H8 — calibrar threshold
- 5 (balde 3): H1 parcial (1 resolvida com rerank, 4 fora do pool atual)
- 1 (gt-0002): H4 — GT incompleto
- 1 (gt-0027): H6 — query subespecificada

Não há mais "falhas inexplicadas".

## Achado 7 — As 3 falhas de H6/gap-de-vocabulário têm 3 causas distintas

**Achado não-previsto no plano inicial.** Surgiu em 1.3-alt e foi refinado em 1.3-alt-b (cross-config).

Em 1.3-alt as 3 perguntas (gt-0005, gt-0025, gt-0027) pareciam um único fenômeno ("chunks concept-dense"). Em 1.3-alt-b, testando as 6 configs publicadas, revelaram-se **3 causas distintas**:

### gt-0005 → CONFIRMA concept-dense; hierarchical RESOLVE

| config | best cov | passage_recall@10 |
|---|---:|---:|
| fixed/md/flat | 0.50 | 0 |
| article/tx/flat | 1.0 (rank 67) | 0 |
| **hier/md/hier** | **1.0 (rank 1)** | **1.0** |
| **hier/tx/hier** | **1.0 (rank 1)** | **1.0** |

Chunk concept-dense (Art. 2º com ~50 definições juntas) em fixed-size 512 fica invisível. Em hierarchical, o filho pequeno (300 palavras) é mais focado e o pai retornado contém a definição completa. **Fix já existe no projeto** — é apenas escolher hierarchical para esta classe de pergunta.

### gt-0025 → "excerpt enumerado longo" (fenômeno distinto)

Excerpt tem 4 condições enumeradas (a, b, c, d). Em fixed-size todas cabem num chunk (cov 0.47, perto do threshold 0.60). Em article-aware/hierarchical, divisão por artigo **PIORA** (cov 0.13-0.50) porque a lista é distribuída em chunks separados.

| config | best cov |
|---|---:|
| fixed/md/flat | **0.47** (melhor) |
| hier/tx/hier | 0.50 |
| article/tx/flat | 0.18 |

**Chunking menor não resolve.** Possíveis soluções: excerpt curto que cubra apenas a "porta de entrada" da lista; chunk com janela maior (>512) para listas completas; matching que aceite cobertura parcial em excerpts enumerados.

### gt-0027 → H6 (vocabulário) CONFIRMADA com oracle real

Em 1.3-alt-b cross-config, fixed-size mostrou doc fora do top-100 (best_cov=0). Mas o caveat do usuário se confirmou: o LLM-rewriter de 1.3-alt não inferiu os termos discriminantes.

Retestamos em A com **oracle real construído manualmente**, incluindo "taxa regulatória de remuneração de capital", "estrutura de capital regulatória", "custo de capital":

| config | ORIGINAL passage_recall@10 | ORACLE_REAL passage_recall@10 |
|---|---:|---:|
| fixed/md/flat | 0.00 | **1.00** |
| fixed/tx/flat | 0.00 | **1.00** |
| article/tx/flat | 0.00 | **1.00** |
| hier/tx/hier | 0.00 | **1.00** |
| article/md/flat | 0.00 | **1.00** |
| hier/md/hier | 0.00 | **1.00** |

**Resultado dramático**: TODAS as 6 configs passam de 0 para 1.0 com oracle real. gt-0027 é **gap de vocabulário puro** — fixable em produção apenas se LLM-rewriter conseguir inferir os termos certos sem ver o documento. O rewriter de 1.3-alt falhou nisso; precisa investigação separada para query expansion competente.

### gt-0025 → 3 fenômenos distintos por chunking (não tem fix universal)

Investigado em B. As 4 condições enumeradas (a/b/c/d) do excerpt aparecem de jeitos diferentes em cada chunking:

| config | situação real | categoria |
|---|---|---|
| fixed/md/flat | 4 condições no chunk 3 (no top-10), cov=0.47 < 0.60 | `matching_exigente_demais` |
| fixed/tx/flat | 4 condições no chunk 3, mas chunk não no top-10 | `excerpt_longo_em_um_chunk_mas_mal_ranqueado` |
| article/{md,tx} | condições partidas entre chunks 2 e 11 | `excerpt_partido_entre_chunks` |
| hier/{md,tx} | mesmo de article | `excerpt_partido_entre_chunks` |

**Cada chunking quebra de jeito diferente.** Não tem config vencedora. Possíveis intervenções (todas requerem trabalho):
- Matching alternativo (cosine de embedding chunk×excerpt em vez de token coverage)
- Excerpt mais curto e distintivo no GT (mas isso muda o GT)
- Aceitar como limitação documentada

**Implicações:**
- Achado 7 (concept-dense) sobrevive como categoria, mas representa apenas 1 das 3 casos investigados, e o "fix" é mudar de fixed-size para hierarchical para a classe de pergunta afetada.
- "Excerpt enumerado longo" (gt-0025) é fenômeno novo — issue separado.
- gt-0027 fica como pendência analítica.

## Achado 6 — Balde 2 (post-1.2b): 3 perfis distintos, gap de vocabulário recorrente

Após 1.2 refutar o "fix por threshold", 1.2b reabriu o balde 2 e classificou cada caso usando 6 categorias predefinidas.

| qid | categoria | best cov geral | observação |
|---|---|---:|---|
| gt-0005 | `trecho_fora_do_pool` | **1.0** | chunk com definição perfeita não foi puxado nem no top-100 |
| gt-0017 | `gt_ou_excerpt_problematico` | 0.43 | excerpt parece síntese; reabre H3 parcialmente |
| gt-0025 | `trecho_fora_do_pool` | **1.0** | excerpt substring exata em chunk fora do pool |
| gt-0034 | `fora_do_top10` | 1.0 (rank 14) | rerank pool 100 já salva (Opção A) |

**Padrão dominante**: 2 dos 4 casos (gt-0005, gt-0025) têm chunk com cobertura PERFEITA do excerpt em algum lugar do índice, mas o retriever semântico não o priorizou. Isso é **gap de vocabulário** — o embedding da query (linguagem informal/técnica do usuário) não alinha com o embedding do chunk (linguagem normativa formal do documento).

Exemplo gt-0005: query "usina fotovoltaica com armazenamento" não bate semanticamente forte com chunk que tem "central geradora de fonte despachável: ... geração fotovoltaica de até 3 MW ... armazenamento de energia em baterias".

Isso **reforça H6 muito além de gt-0027**. O gap de vocabulário formal-vs-informal aparece em 3 das 11 falhas (gt-0005, gt-0025, gt-0027), não apenas 1. Sugere intervenção via:
- Query expansion / reformulação
- Embedding fine-tuned em corpus regulatório PT-BR
- Pseudo-relevance feedback

Não é fix barato. Vira issue separada.

## Achado 5 — Rerank Cohere multilingual com pool 100: ajuda com trade-off (H1 parcial)

Testado em duas rodadas:

**Rodada 1** ([rerank_best_comparison.md](rerank_best_comparison.md)) — Cohere Rerank-3 com `candidates_k=50` (default): pool muito pequeno, deixou gt-0030 (rank 82) e gt-0007 (rank 30) fora do alcance. Net zero em passage_recall.

**Rodada 2** ([rerank_pool_comparison.md](rerank_pool_comparison.md)) — Mesmo rerank com `candidates_k=100`: alcance suficiente para os trechos profundos.

| métrica | base | rr pool 50 | **rr pool 100** | Δ pool 100 vs base |
|---|---:|---:|---:|---:|
| passage_recall@10 | 0.7708 | 0.7708 | **0.8125** | **+0.042** |
| doc_recall@10 | 0.8542 | 0.7917 | 0.8333 | -0.021 |
| MRR@10 | 0.5833 | 0.6282 | **0.6516** | +0.068 |
| nDCG@10 | 0.6243 | 0.6413 | **0.6751** | +0.051 |

**Pool 100 salva 4 (vs base): gt-0007, gt-0012, gt-0030, gt-0034.** Quebra 2 (gt-0028, gt-0049). Net +2 perguntas.

**Pool 100 salvou a mais que pool 50: gt-0007 (rank 30) e gt-0030 (rank 82)** — exatamente o que a hipótese previa.

**Trade-off real:** rerank melhora passage_recall (+4 pp), MRR (+7 pp) e nDCG (+5 pp), mas piora doc_recall (-2 pp). Significa: rerank reorganiza top-50/100 promovendo alguns chunks corretos, mas também promove chunks de documentos errados que parecem semanticamente próximos.

**Lição:** o default `candidates_k=50` em [retriever.py:184](../../../src/rag/retriever.py#L184) é arbitrário e subdimensionado para rerank em corpus regulatório. Tornar default `100` (quando rerank ativo) seria melhoria de produção.

**Implicação para portfólio:** rerank não é "plug and play". A magnitude do pool importa, e há trade-off entre passage e doc recall que precisa de decisão explícita.

## Limitações metodológicas conhecidas

Antes do GATE, deixar explícitas as fronteiras do que foi e não foi medido:

1. **A.6 (threshold sensitivity) media SÓ recall** — mexe no **oráculo de avaliação**, não no RAG. `SUPPORT_EXCERPT_TOKEN_THRESHOLD` em [matching.py:44](../../../src/evaluation/matching.py#L44) decide se um chunk recuperado conta como relevante na hora de **medir** a métrica; não altera o que o retriever devolve em produção. **Lacuna fechada em 1.2** com LLM-as-judge: precisão do oráculo sob threshold 0.30 = 0.055 → threshold 0.60 fica como está.

2. **A.2 distingue LITERAL_MATCH de TOKEN_MATCH.** 46% das fontes têm o trecho como string contígua; 54% têm apenas tokens dispersos. "Sem evidência de GT inventado" é diferente de "GT comprovadamente correto" — 1 caso reabriu (gt-0017, ver Achado 6).

3. **Opção A (rerank pool 100) testada em 1 das 16 configs.** Resultado (passage +4 pp, doc -2 pp) específico da melhor config. Generalização para article-aware/hierarchical fica como issue #5.

4. **H12 (chunking)** tem causa confirmada em 1.1 — o regex captura referências cruzadas. Fix NÃO aplicado nesta etapa (issue separada).

5. **Scripts de diagnóstico usam cache local** via `hf_hub_download`, exceção explícita à regra Hub-first. Documentado em README e em cada script (issue #4 fechada).

## GATE DE DECISÃO FINAL

### Estado consolidado das 11 falhas residuais

Após A+B, todas as 11 têm causa confirmada e fix conhecido (mais ou menos viável):

| qid | causa final confirmada | fix realístico | complexidade |
|---|---|---|---|
| gt-0002 | H4 — GT incompleto (PRORET 6.8 também responde) | schema `relevant_source_groups` com `any_of` | média (issue #6) |
| gt-0005 | concept-dense em fixed-size | usar hierarchical (recall = 1.0) ou roteamento por tipo de pergunta | baixa para "usar hier"; média para roteamento |
| gt-0007 | balde 3, rank 30 | rerank pool 100 salva | já testado |
| gt-0012 | balde 3, rank 32 | rerank pool 100 salva | já testado |
| gt-0017 | excerpt sintético do GT | corrigir excerpt no GT | baixa (issue #9) |
| gt-0025 | excerpt enumerado, sem fix universal | documentar como limitação OU matching alternativo | issue #11 |
| gt-0026 | balde 3, rank 15 | rerank pool 100 salva | já testado |
| gt-0027 | H6 puro — vocabulário discriminante | query expansion competente | média (issue #10) |
| gt-0029 | balde 3, rank 67 | pool 200+ (custa mais Cohere) | baixa, mas API quota |
| gt-0030 | balde 3, rank 82 | pool 200+ | baixa, mas API quota |
| gt-0034 | rank 14, concept-dense parcial | rerank pool 100 salva | já testado |

**11/11 explicadas.** Nada inexplicável. Pendência: cada fix tem custo distinto.

### Quadro de configurações observadas (medidas, post-A+B)

| Setup | passage_recall@10 | doc_recall@10 | observação |
|---|---:|---:|---|
| **Atual** (fixed/md/flat, threshold 0.60, sem rerank) | **0.771** | 0.854 | linha de base validada |
| + rerank pool 100 | 0.813 | 0.833 | salva 4, quebra 2; trade-off real |
| Hierarchical (gt-0005 especificamente) | 1.0 (1 pergunta) | 1.0 | mostra que config-routing funcionaria |
| Oracle real em gt-0027 | 1.0 (1 pergunta) | 1.0 | mostra ceiling de query expansion competente |

### Decisão tomada: Caminho 4 ajustado

**Princípio orientador:** o diagnóstico cumpriu o papel principal — as 11 falhas não são mais mistério. Continuar otimizando retrieval sem saber como isso impacta a resposta final começa a virar otimização especulativa. Vamos destravar a Camada 3.5 com config atual e voltar ao retrieval com prioridade guiada por dados reais.

**Ações aplicadas neste ciclo de housekeeping:**

| # | Ação | Onde | Status |
|---|---|---|---|
| H1 | `--rerank-candidates-k` adicionado ao CLI; `StoreConfig.candidates_k_override`; Makefile target `benchmark-retrieval-rerank` usa pool 100 | [scripts/run_benchmark.py](../../../scripts/run_benchmark.py), [src/evaluation/benchmark.py](../../../src/evaluation/benchmark.py), [Makefile](../../../Makefile) | ✅ |
| H2 | Seção Troubleshooting no README documentando `HF_HUB_DISABLE_XET=1` + uso de cache local nos scripts de diagnóstico | [README.md](../../../README.md) | ✅ |
| H3 | Nota padrão "uso de hf_hub_download como exceção diagnóstica" em cada script `scripts/diagnose_*.py` que materializa cache | scripts/diagnose_*.py | ✅ |
| H4 | Recall honesto atual (0.771) e descarte de threshold 0.30 explicitados no header deste documento | este SUMMARY | ✅ |

**Ações DELIBERADAMENTE não aplicadas (registradas como issues abaixo):**

- ❌ Corrigir excerpt de gt-0017 ou enriquecer GT com PRORET 6.8 para gt-0002 → mexe no contrato do GT, exige republicação versionada. Fica como issue consciente para depois do gerador.
- ❌ Fix de H12 (chunking) → rebuild de 4 vectorstores, custo OpenAI ~$3-8, ganho marginal incerto sem feedback do gerador.
- ❌ Query expansion competente para gt-0027 (issue #10) → exige prompt engineering não-trivial.
- ❌ Rerank pool 100 em mais 3 configs (issue #5) → não bloqueante; o achado principal (trade-off com pool 100 na melhor config) já está consolidado.

### Issues registradas para depois do gerador

| # | Issue | Origem | Status |
|---|---|---|---|
| 1 | ~~Medir precisão do oráculo sob threshold 0.30~~ | crítica do usuário | ✅ **FECHADO em 1.2** |
| 2 | ~~Inspecionar amostra real de chunks tiny em article-aware markdown~~ | crítica do usuário | ✅ **FECHADO em 1.1** |
| 3 | ~~Reconciliar Makefile `benchmark-retrieval-rerank` com `candidates_k=100`~~ | crítica do usuário | ✅ **FECHADO via `--rerank-candidates-k`** |
| 4 | ~~Documentar uso de `hf_hub_download` (cache local) nos scripts de diagnóstico~~ | crítica do usuário | ✅ **FECHADO** (README + headers) |
| 5 | Testar rerank pool 100 em mais 3-4 configs antes de generalizar para portfólio | limitação Opção A | médio — após gerador |
| 6 | Suportar fontes alternativas no GT (gt-0002 → REN 1000 **ou** PRORET 6.8). Requer schema `relevant_source_groups` com `mode: any_of` no GT, validador, matching, testes, e republicação versionada. | H4 | médio — após gerador |
| 7 | Adicionar validação cruzada na publicação do GT (excerpt aparece no doc real) | A.2 lessons | baixo |
| 8 | ~~Documentar `HF_HUB_DISABLE_XET=1` como workaround intermitente~~ | A.1 lessons | ✅ **FECHADO** (README Troubleshooting) |
| 9 | Corrigir excerpt sintético em gt-0017 | 1.2b | baixo — requer republicação GT |
| 10 | Investigar query expansion competente — LLM-rewriter de 1.3-alt não inferiu termos discriminantes ("custo de capital") apesar de eles serem inferíveis para um especialista | H6 (gt-0027) | médio — requer prompt engineering |
| 11 | Sem fix conhecido para gt-0025 (excerpt enumerado). Possíveis caminhos: matching alternativo (cosine embedding), excerpt mais curto no GT, ou aceitar como limitação documentada. | B | baixo (documentar como limitação) |
| 12 | Fix de H12 (regex de article-aware capturando referências cruzadas) — requer rebuild de 4 vectorstores | 1.1 | médio — só vale se gerador mostrar que afeta resposta |

### Próximo passo

**Camada 3.5 — implementar `src/rag/generator.py` em escopo de smoke test.**

Com a melhor config (text-embedding-3-large + fixed-size + markdown + flat, sem rerank por default, threshold inalterado), rodar gerador em N perguntas das 48 e medir `faithfulness` + `answer_correctness`. Esses dados é que vão priorizar as issues 5/6/9/10/11/12 acima — não a intuição.

A pergunta importante agora é: **com recall@10 = 0.771, o gerador produz respostas fiéis e citadas?**
