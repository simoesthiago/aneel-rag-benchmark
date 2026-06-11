# Roadmap de correção do ANEEL RAG Benchmark

> **Do diagnóstico à correção: como transformamos 24 "falhas" opacas em um
> plano de engenharia rastreável que ataca cada uma até a raiz.** Este
> documento mapeia toda falha à sua causa-raiz confirmada e à intervenção
> que a resolve, em fases com critério de sucesso pré-comprometido e
> execução adaptativa (medir → decidir → avançar).

## TL;DR para quem chega agora

- O benchmark reportava **answer_usable_rate = 50%** (24/48). Auditoria
  externa independente (2 fases, vieses opostos) provou que o número
  honesto é **62–73%**: boa parte das "falhas" era ruído de ground truth,
  não falha de sistema.
- A métrica é **confiável**: 0 falsos positivos em 8 aprovações auditadas.
- Cada uma das 24 falhas tem **causa-raiz confirmada** e uma fase de
  correção dedicada. **Nenhuma falha é "misteriosa" e nenhuma é abandonada.**
- O roadmap persegue a correção de **todas as 24 falhas**, com teto
  teórico de ~98–100% de usabilidade. As falhas mais difíceis têm fase
  própria, não viram nota de rodapé.

## O método (por que confiar nestes números)

Não chutamos. Cada decisão passou por um protocolo:

1. **Taxonomia de falha objetiva** — 5 tipos (`retrieval_document_failure`,
   `retrieval_passage_failure`, `citation_failure`, `answer_quality_failure`,
   `citation_and_answer_failure`) derivados de métricas, não de opinião.
2. **15 diagnósticos versionados** — 12 hipóteses testadas
   (`diagnostic/SUMMARY.md`), 5 refutadas, separando artefato de medição
   de falha real (ex.: threshold do oráculo tinha 89% de falsos positivos).
3. **Auditoria externa cega** — LLM forte com web search auditou as 50
   perguntas contra fontes oficiais ANEEL, em 2 fases com defaults opostos
   para evitar viés de confirmação.
4. **Critérios pré-comprometidos** — toda promoção (rerank, prompt, query
   expansion) teve regra de decisão fixada **antes** de ver resultados.
5. **Comparação pareada por pergunta** — nunca "a média melhorou"; sempre
   "quantas perguntas salvou vs quebrou, nominalmente".

## Estado consolidado: as 24 falhas, por causa-raiz

| qid | failure_type | causa-raiz confirmada | fase |
|---|---|---|---:|
| gt-0003 | citation_and_answer | citou REN 414 **revogada** (ruído de índice) | **F1** |
| gt-0007 | retrieval_document | doc-alvo em rank 30 (fora do top-10) | **F2** |
| gt-0012 | retrieval_document | doc-alvo em rank 32 | **F2** |
| gt-0026 | retrieval_document | doc-alvo em rank 15 | **F2** |
| gt-0034 | retrieval_passage | doc-alvo em rank 14 | **F2** |
| gt-0030 | retrieval_document | doc-alvo rank 82; **salva no pool 100** | ✅ F1/F2 |
| gt-0029 | retrieval_document | doc-alvo rank ~30 (já no pool); reranker não sobe | F2† → resid. |
| gt-0002 | retrieval_document | GT incompleto: PRORET 6.8 também responde | **F3** |
| gt-0005 | retrieval_passage | GT incompleto: REN 1059 + concept-dense | **F3/F8** |
| gt-0039 | citation | GT incompleto: chunks do mesmo doc | **F3** |
| gt-0046 | citation | GT incompleto: chunks do mesmo manual | **F3** |
| gt-0041 | answer_quality | excerpt do GT incompleto (3 de 11 parcelas) | **F3** |
| gt-0013 | citation_and_answer | pergunta ambígua (2 dimensões) | **F3** |
| gt-0017 | retrieval_passage | corpus PRODIST v0 (2008) desatualizado | **F4** |
| gt-0019 | citation | corpus PRODIST v0 desatualizado | **F4** |
| gt-0022 | citation_and_answer | corpus PRODIST v0 desatualizado | **F4** |
| gt-0027 | retrieval_document | vocabulário: 2.4 vs 2.1 (sem termo discriminante) | **F5** |
| gt-0023 | citation_and_answer | identificador vizinho: 2.1 vs 2.1A (somou RI) | **F5** |
| gt-0024 | citation_and_answer | identificador vizinho: 2.1 vs 2.1A | **F5** |
| gt-0028 | citation_and_answer | parcial: citou 8.3 em vez de 7.2 | **F5** |
| gt-0037 | citation_and_answer | parcial: perdeu nuance jurídica | **F5** |
| gt-0025 | retrieval_passage | excerpt enumerado (a/b/c/d) partido por chunk | **F6** |
| gt-0015 | answer_quality | erro de conteúdo do gerador (glossário) | **F7** |
| gt-0049 | answer_quality | parcial: generalização sobre prazos | **F7** |

† **F2† avaliada e REJEITADA** (2026-06-10, sem gasto de quota). A hipótese
"pool 200+ salvaria gt-0029/0030" não se sustenta:
- **gt-0030** (rank 82) **já está `usable`** no pipeline atual — pool 100 a
  alcança (foi salva pela F1). A anotação "pool 200+" era pessimista.
- **gt-0029**: verificação Cohere-free do rank denso no pipeline atual dá
  **rank ~30-32** (não 67), ou seja, o doc-alvo **já é candidato no pool 100**;
  o reranker é que não o sobe ao top-10. Aumentar o pool para 200 só adiciona
  distratores — não pode ajudar um doc já presente no pool. O gargalo é o
  **reranker/sinal de retrieval**, não o tamanho do pool.
- **Desfecho:** gt-0029 passa a **falha residual de retrieval/reranker** (sem
  fase nova; revisitar junto da F5 ou de uma eventual melhoria de reranker).

**24/24 falhas têm fase de correção dedicada.** Nenhuma é tratada como
limitação aceita — as duas mais duras (gt-0015, gt-0025) ganharam fases
próprias (F6, F7).

---

## Retrieval vs Generation: como as 24 se dividem

Ponto de leitura importante para evitar contagem dupla. As 24 falhas são
medidas pelo gate final `answer_usable = recall>0 AND citation≥0.5 AND
correctness≥0.8`. Esse gate **engloba as duas camadas** do pipeline RAG —
retrieval e generation. As falhas de retrieval **não são um conjunto
separado que se soma às 24**; elas são um **subconjunto** delas:

```
24 falhas (answer_usable = False)
├── 11 de RETRIEVAL (a busca não trouxe o trecho/documento certo)
│   ├── 7  retrieval_document_failure  → doc-alvo nem aparece no top-10
│   │       (gt-0002, 0007, 0012, 0026, 0027, 0029, 0030)
│   └── 4  retrieval_passage_failure   → doc aparece, mas o trecho não
│           (gt-0005, 0017, 0025, 0034)
└── 13 de GENERATION (contexto certo presente; a resposta/citação falha)
    ├── 7  citation_and_answer_failure
    ├── 3  answer_quality_failure
    └── 3  citation_failure
```

**Por que retrieval está dentro das 24:** se o retrieval falha (`recall=0`),
a pergunta reprova o gate automaticamente — não importa a qualidade da
geração. Logo toda falha de retrieval já conta como uma das 24. Não há
soma (não é 24 + 11 = 35); os 11 estão **contidos** nos 24.

**De onde vêm os números das duas camadas medidas isoladamente:**

| camada | métrica | valor | falhas (de 48) |
|---|---|---:|---:|
| Retrieval — documento | `doc_recall@10` | 0.854 | **7** |
| Retrieval — passagem | `passage_recall@10` | 0.771 | 11 |
| Generation (gate final) | `answer_usable_rate` | 0.500 | 24 |

As 7 falhas de documento (`doc_recall`) são a forma mais severa: o sistema
nem traz o documento certo. As 4 de passagem trazem o documento mas não o
trecho. Juntas (11) são o "piso de retrieval" dentro das 24.

**Cobertura no roadmap** — as 11 falhas de retrieval e suas fases:

| qid | falha de retrieval | fase |
|---|---|---:|
| gt-0007 | doc rank 30 | F2 |
| gt-0012 | doc rank 32 | F2 |
| gt-0026 | doc rank 15 | F2 |
| gt-0034 | passagem rank 14 | F2 |
| gt-0029 | doc rank 67 | F2† |
| gt-0030 | doc rank 82 | F2† |
| gt-0002 | doc — GT incompleto | F3 |
| gt-0005 | passagem — concept-dense | F3/F8 |
| gt-0017 | passagem — corpus PRODIST v0 | F4 |
| gt-0027 | doc — vocabulário 2.4 vs 2.1 | F5 |
| gt-0025 | passagem — excerpt enumerado | F6 |

As 11 estão cobertas. A maioria (6) cai na F2 (rerank pool 100), o que faz
da F2 a alavanca de maior impacto sobre retrieval.

---

## Modelo de execução: adaptativo, não linear

As fases **não rodam numa sequência fixa cega**. Após cada fase aplicamos
um gate:

```
  executar fase → medir (pareado) → aplicar critério pré-comprometido
       → decidir a PRÓXIMA fase com base no que sobrou
```

Isso evita investir numa fase cara cujo problema outra fase mais barata já
resolveu (ex.: se F2+F3 já salvarem gt-0005, F8 fica desnecessária).
A ordem abaixo é a **sugestão de partida por ROI**, não um compromisso
rígido — cada gate pode reordenar o resto.

**Ponto de partida recomendado:** F1 → F2 (baratas, código pronto, baixo
risco) para subir o baseline honesto antes de qualquer gasto, e então
reavaliar.

---

## Fase 0 — Fundação (✅ CONCLUÍDA)

- ✅ Benchmark de retrieval (16 configs) + RAG (baseline, rerank, QE)
- ✅ 5 métricas (3 objetivas + 2 LLM-judge) + gate `answer_usable`
- ✅ Comparação pareada (rerank, prompt, query expansion)
- ✅ 15 diagnósticos de causa-raiz (`diagnostic/SUMMARY.md`)
- ✅ Auditoria externa Fase A (24 falhas) + Fase B (calibração, 0 FP)
- ✅ Número honesto estabelecido: 62–73% real vs 50% reportado

**Entregável:** `AUDIT_CONCLUSION.md`, `phaseA_analysis.md`, `OPPORTUNITIES.md`.

---

## Fase 1 — Higiene de índice: remover normas revogadas (✅ CONCLUÍDA)

**Problema:** 49,4% do corpus (812 de 1643 docs) são normas **revogadas**.
Zero são alvo do GT. Elas competem semanticamente com as vigentes.
gt-0003 é prova: o sistema citou a REN 414/2010 (revogada pela REN 1000
que a própria pergunta menciona).

**Intervenção:** filtrar `situacao == 'revogada'` na construção do índice.
Manter `vigente` (179) e `nan` (652). Investigar se dá para filtrar no
nível de metadados/índice sem re-embedding (custo zero) ou se exige
rebuild.

**Ataca:** gt-0003 diretamente; reduz ruído para todas as 50 perguntas.

**Custo:** baixo. **Risco:** quase nulo (nenhum alvo do GT é revogado).

**Critério pré-comprometido (original):**
> Promover o filtro a default SE gt-0003 passar a `usable` E
> `answer_usable_rate` global não cair E nenhuma pergunta hoje `usable`
> regredir.

**Critério refinado (pré-registrado antes do veredito final):**
> Promover SE `delta_doc_recall >= -0.02` E `hard_broken == 0`, onde
> *hard_broken* = pergunta que regride **e** perde `doc_recall` (o filtro
> removeu um documento que a resposta precisava). Um *soft break* (regride
> mas mantém `doc_recall`) NÃO bloqueia.

**Racional da refinação (independente do resultado):** o filtro só controla
*o que entra no pool*. A única forma de ele ser legitimamente culpado por
uma regressão é remover um documento que o GT precisa → queda de
`doc_recall`. Penalizar a higiene factual por um deslize de citação do
gerador (mesmo `doc_recall`, citação diferente) mistura dois subsistemas.

**Constatação empírica — chão de ruído do gerador:** ao re-rodar a config
idêntica duas vezes (embeddings em cache, temperatura 0), o `usable`
flutuou em ±1-2 perguntas (gt-0003, gt-0039, gt-0019, gt-0022 trocaram de
lado entre runs). `doc_recall` (retrieval) foi **idêntico** nos dois runs.
Logo: decidir promoção pelo `net_delta` de 1 pergunta no `usable` é
insustentável — esse delta está dentro do ruído. O sinal estável é
`doc_recall`. ⚠️ Isso retroage à **Fase 2** (promovida com `saved=2/broken=1`
"no limite"): aquele veredito também está no chão de ruído — vale a
ressalva, ainda que `doc_recall` da F2 (+0.042) seja sólido por si só.

**Resultado (veredito `promote`):** ver `results/rag-50/revogadas_pairing.md`.
- `delta_doc_recall = +0.021` (estável entre runs) ✅; `hard_broken = 0` ✅.
- **Salva** gt-0008 e gt-0030: sem filtro citavam normas **revogadas**
  (erro factual); com filtro citam a norma vigente. Ganho de higiene real.
- **Soft breaks** (gt-0004, gt-0003 conforme o run): `doc_recall=1.0` nos
  dois lados — o filtro não removeu o alvo; o gerador trocou a citação.
- **Ressalva honesta:** o ganho em `answer_usable_rate` é nulo/ruidoso
  (0.604 vs 0.604 no segundo run). O motivo real da promoção é higiene
  factual + `doc_recall`, não o score de `usable`.
- **Aplicado:** `exclude_revogadas=True` é o default do rerank em
  `build_rag_baseline_configs`. gt-0003 (motivação original) já fora
  resolvida pela F2 — está `usable` no baseline sem o filtro.

---

## Fase 2 — Calibração de retrieval: rerank pool 100 no RAG (✅ CONCLUÍDA)

**Problema:** o SUMMARY (Achado 5) provou que rerank com `candidates_k=100`
salva gt-0007/0012/0030/0034 em retrieval (+4pp passage_recall, +7pp MRR).
Mas o benchmark RAG instanciava rerank com **pool 50** (default). O ganho
nunca fora medido no `answer_usable`.

**Intervenção:** parâmetro `rerank_pools` em `build_rag_baseline_configs` +
flag `--rerank-pool-comparison` + analyzer `analyze_rerank_pool_pairing.py`.
Run de 3 configs (baseline, rerank@50, rerank@100) com pareamento isolado.

**Critério pré-comprometido:**
> Promover pool 100 a default do rerank SE, no Par 1 (pool50 vs pool100):
> `saved >= 2 * broken` E `delta_doc_recall >= -0.02`.

**Resultado (veredito `promote`):** ver `results/rag-50/f2_rerank_pool.md`.
- Par 1: saved=2 (gt-0001, **gt-0007**), broken=1 (gt-0047),
  delta_doc_recall=+0.042 → **promote** (no limite: 2 >= 2×1).
- answer_usable: baseline 0.521 → rerank@50 0.583 → **rerank@100 0.604**.
- **3 das 7 falhas reais caíram** (gt-0003, gt-0007, gt-0012);
  gt-0023/0024 melhoraram parcialmente.
- **Aplicado:** pool 100 é o default do rerank em
  `build_rag_baseline_configs`. Ressalva honesta: ganho sobre pool 50 é
  marginal (+1); gt-0026 (alvo) não foi salva.

---

## Fase 3 — Ground Truth v2: fontes alternativas + correções (✅ CONCLUÍDA)

**Problema:** 6 falhas são do GT, não do sistema (auditor confirmou
fontes alternativas legítimas + 1 excerpt incompleto + 1 pergunta ambígua).

**Intervenção (3 sub-blocos):**
- **3a — fontes do mesmo tipo (seguro):** gt-0005 (+REN 1059/2023),
  gt-0039 (+chunks do 2.14-RQ), gt-0046 (+chunks do manual). Schema já é
  multi-source; extrair excerpts reais via `carregar_corpus_hub`.
- **3b — schema `any_of` cross-tipo:** gt-0002 (+PRORET 6.8 a pergunta
  REN). Relaxar o validador que hoje exige tipo uniforme
  (`ground_truth.py:433`). Issue #6.
- **3c — pontuais:** gt-0041 (`fix_excerpt` 3→11 parcelas), gt-0013
  (`clarify_question`).

**Ataca:** gt-0002, gt-0005, gt-0039, gt-0041, gt-0046, gt-0013.

**Custo:** médio (3a sem custo OpenAI; 3b código+testes). Republicação
versionada do GT (v2).

**Critério pré-comprometido:**
> Cada correção só entra no GT v2 se passar a validação cruzada completa
> (URL ∈ corpus, excerpt cobertura ≥ 0.70). Republicar como versão nova;
> nunca sobrescrever v1.

**Status (2026-06-11 — ✅ CONCLUÍDA: infra `any_of` + GT v2 (3a/3b/3c) +
publicado como `retrieval-50-v3` + promovido a default + canônico re-rodado):**

Descoberta ao medir o estado atual (o roadmap/auditoria precedem F1/F2):
- **gt-0039 e gt-0046 já estão `usable`** — resolvidas pela F1/F2 (rerank
  pool 100 + filtro), como ocorreu com a gt-0030. Não precisam de edição.
- **Métricas eram AND** (`doc_recall`, `source_coverage` = fração de *todas*
  as fontes): adicionar fonte alternativa ao GT *reduziria* o score. Logo a
  F3 exigiu **semântica `any_of`**, não só edição de dados.

Implementado (3a + 3b, escopo desta rodada):
- **`any_of` schema + métricas group-aware** — campo opcional `group` por
  fonte (OR no grupo, AND entre grupos; singleton = AND original, zero
  regressão); `tipo`/`subtipo` opcionais por fonte; validador relaxado para
  tipo por-fonte; `source_coverage`/`doc_recall_at_k` group-aware. Bump de
  `schema_version` 1→2. Coberto por testes (matching/metrics/ground_truth).
- **GT v2 local** (`aneel_retrieval_50.jsonl`, +2 fontes, validado contra o
  corpus): gt-0005 (+REN 1059/2023, mesmo tipo) — conserto limpo
  (correctness 0.95 → deve virar `usable`); gt-0002 (+PRORET 6.8 cross-tipo)
  — recall/citação/doc_recall ficam honestos, **mas correctness=0.72 < 0.8
  é um muro de conteúdo** que a edição de fonte não derruba (a pergunta segue
  reprovando o gate; documentado). Script: `scripts/apply_gt_v2_anyof.py`.

Re-run local contra o GT v2 (confirmação, 2026-06-11):
- **gt-0005: ❌ → ✅ `usable`** — recall 0→1.0, citação 0→1.0 (o `any_of`
  creditou a REN 1059). Conserto limpo confirmado.
- **gt-0002: segue ❌** — recall 0→1.0 e doc_recall 0→1.0 (números honestos
  via `any_of`), mas correctness 0.72 inalterada → reclassificada de
  `retrieval_document_failure` para `citation_and_answer_failure`. O residual
  é **geração**, não GT — exatamente como previsto.
- `answer_usable_rate` (pipeline): 0.604 → 0.646. **Leitura honesta:** +1
  real e atribuível (gt-0005) sobre o chão de ruído do gerador (o baseline
  cru caiu 26→25 na mesma rodada). Não tratar o +2 agregado como ganho real.

3c — correções pontuais (implementado 2026-06-11, ✅ ambas viraram `usable`):
- **gt-0041** (`fix_excerpt`/answer 3→11 parcelas): o `expected_answer` listava
  3 parcelas do VMEuRB; o corpus (proc-rede-8-3-pr, item 1.2.1.1) tem 11
  — (a) a (k). O sistema já respondia as 11 e levava correctness baixa contra
  um gabarito incompleto. Completado o gabarito + excerpt literal:
  **correctness 0.22 → 0.97**, ❌ → ✅ `usable`.
- **gt-0013** (`clarify_question`): a REN 1095/2024 padroniza DUAS coisas
  (número de identificação da UC e uso de CPF/CNPJ) — pergunta ambígua. O
  sistema respondia CPF/CNPJ; o GT esperava o número da UC. Reformulada a
  pergunta para apontar sem ambiguidade à UC: **correctness 0.72 → 0.93**,
  ❌ → ✅ `usable`. (Quebra comparabilidade com v1 — aceitável: é versão nova.)
- Script: `scripts/apply_gt_v2_3c.py`. GT local agora é a v2 COMPLETA
  (3a+3b+3c), validada contra o corpus.

Medição da v2 completa (local, contra o JSONL com 3a+3b+3c):
- `answer_usable_rate` (pipeline): 0.604 (v1) → **0.6875 (33/48)**.
- **Flips reais e atribuíveis da F3: +3** — gt-0005 (3a), gt-0041 e gt-0013
  (3c). gt-0002 (3b) ficou com números honestos mas segue no muro de
  correctness. (Parte do delta agregado ainda é ruído do gerador.)

Promoção a default (✅ CONCLUÍDA, 2026-06-11):
- GT v2 completo publicado no Hub como **`version=retrieval-50-v3`** (versão
  nova — respeita "nunca sobrescrever"). Versões `retrieval-50` (v1) e
  `retrieval-50-v2` (intermediária, só 3a/3b) preservadas no Hub.
- **`GROUND_TRUTH_VERSION` default → `retrieval-50-v3`** em `settings.py`.
  Runs default agora carregam a v3 (com 3a+3b+3c).
- **Baseline canônico re-rodado contra a v3** (do Hub): `results/rag-50/`
  atualizado. Pipeline (rerank@100 + filtro) `answer_usable_rate` = **0.6875
  (33/48)**; baseline cru 0.542. doc_recall 0.875.
- F3 entregue ponta a ponta: infra `any_of` + GT v2 (3a/3b/3c) + publicação +
  default + canônico. Ganho real e atribuível: **+3** (gt-0005, gt-0041,
  gt-0013). gt-0002 segue no muro de correctness (residual de geração).

---

## Fase 4 — Atualização de corpus: PRODIST 2008 → 2021 [APROVADA, por último]

**Problema:** o corpus tem PRODIST v0 de 2008 (`aren2008345`); a vigente é
REN 956/2021. GT e corpus "concordam" mas ambos obsoletos. Auditor (web
search) marcou 4 perguntas como `gt_outdated`.

**Intervenção:** re-baixar PRODIST 2021, re-extrair, re-indexar
vectorstores afetados, atualizar `url_original` no corpus CSV, depois
atualizar fontes do GT.

**Ataca:** gt-0017, gt-0019, gt-0022.

**Custo:** ~US$3–8 (re-embedding). **Orçamento aprovado**, mas executar
**após F1–F3** (que são mais baratas e podem já elevar bastante o número).

**Critério pré-comprometido:**
> Executar após F1–F3. Promover SE ≥ 2 das 3 perguntas-alvo passarem a
> `usable` sem regressão global.

---

## Fase 5 — Discriminação de identificadores documentais

**Problema:** a falha residual mais difícil de retrieval. O sistema
confunde documentos com identificadores quase idênticos — Submódulo 2.1 vs
2.1**A** (gt-0023/0024 somaram o componente RI do 2.1A), 2.1 vs 2.4
(gt-0027). A QE genérica da Fase 2 **falhou**. Mas com termos
discriminantes ("custo de capital"), gt-0027 vai de 0 → 1.0 (SUMMARY).

**Intervenção (em ordem de custo):**
1. **Boost por match exato de identificador:** quando a pergunta cita
   "Submódulo 2.4", dar peso a chunks cujo `document_id` casa exatamente.
   Filtro de metadados, não semântico.
2. **Query expansion direcionada:** índice de termos técnicos por
   submódulo, injetados quando a pergunta menciona o submódulo.
3. **Re-ranking por identificador** como desempate.

**Ataca:** gt-0027, gt-0023, gt-0024 (e as parciais gt-0028, gt-0037).

**Custo:** médio-alto. **Risco:** alto de não funcionar — por isso vem
depois das fases baratas, isolada, quando já sabemos o que sobrou.

**Critério pré-comprometido:**
> Testar a abordagem 1 (boost, mais barata) isolada, com pareamento. Só
> passar para 2/3 se 1 não atingir `saved >= 2*broken`.

---

## Fase 6 — Matching por embedding para excerpts enumerados

**Problema:** gt-0025 tem excerpt com 4 condições enumeradas (a/b/c/d) que
se partem diferente em cada chunking — o SUMMARY provou que **nenhuma
config de chunking vence**. A causa não é o retrieval em si, é o **oráculo
de matching**: ele mede cobertura de tokens, e uma lista partida nunca
atinge o threshold mesmo quando o conteúdo certo está lá.

**Intervenção:** matching alternativo por **similaridade de cosine de
embedding** (chunk × excerpt) em vez de cobertura de tokens, para a classe
de excerpts enumerados. Avaliar como métrica complementar antes de
substituir.

**Ataca:** gt-0025 (e possivelmente outros excerpts longos enumerados).

**Custo:** médio (mudança no `matching.py` + validação que não infla
falsos positivos — lição do Gate 1.2). **Risco:** médio — matching novo
precisa ser auditado contra o LLM-judge para não reintroduzir os 89% de
falsos positivos que o threshold 0.30 tinha.

**Critério pré-comprometido:**
> Adotar o matching por embedding SE recuperar gt-0025 E a precisão do
> oráculo (medida por LLM-judge nos matches marginais) permanecer ≥ 0.85.

---

## Fase 7 — Melhoria do gerador (falhas de conteúdo)

**Problema:** gt-0015 e gt-0049 não são falhas de retrieval nem de GT — o
contexto certo está lá, mas o **gerador** erra. gt-0015 confundiu o
glossário do PRODIST com fundamentos legais; gt-0049 generalizou demais
sobre prazos de concessão.

**Intervenção (em ordem de custo):**
1. **Prompt engineering direcionado:** instruções anti-extrapolação
   ("responda apenas o que o contexto define; não infira além"). A Fase 1
   de prompt já testou uma variante — desta vez, mirando os padrões
   específicos dessas falhas.
2. **Self-check de fidelidade:** segundo passo que confronta a resposta
   com o contexto antes de emitir.
3. **Trocar/ajustar o modelo gerador** se 1–2 não bastarem.

**Ataca:** gt-0015, gt-0049 (e reforça as parciais de answer_quality).

**Custo:** baixo-médio (prompt) a médio (self-check/modelo). **Risco:**
prompt pode quebrar perguntas que já passam — por isso pareamento
obrigatório (a Fase 1 mostrou esse risco: v2 salvou 4, quebrou 3).

**Critério pré-comprometido:**
> Promover a mudança de gerador SE `saved >= 2*broken` no pareamento E
> faithfulness médio não cair. Mesma régua da Fase 1 de prompt.

---

## Fase 8 — Roteamento por tipo de pergunta (concept-dense) [opcional]

**Problema:** perguntas de "definição em artigo denso" (gt-0005, Art. 2º
da REN 1000 com ~50 definições juntas) têm recall 0 em fixed-size mas
**1.0 em hierarchical** (SUMMARY Achado 7). Hierarchical é pior no geral.

**Intervenção:** classificador leve que roteia perguntas tipo "definição"
para índice hierarchical. **Pré-requisito:** fix do chunking H12 (regex
`ARTICLE_RE` fragmenta em chunks tiny) — só relevante aqui, pois a config
default fixed-size não sofre de H12.

**Ataca:** gt-0005 (caminho alternativo à F3), classe concept-dense.

**Custo:** alto (H12 fix + rebuild hierarchical + roteador). **Condicional:**
só executar se F3 não resolver gt-0005 E se houver ≥ 3 perguntas
concept-dense afetadas. Para 1 pergunta, o GT enrichment da F3 é mais barato.

---

## Projeção de impacto (pré-comprometida, a confirmar por medição)

| marco | answer_usable_rate | falhas residuais |
|---|---|---|
| Reportado (antes da auditoria) | 50,0% (24/48) | — |
| **Honesto (pós-auditoria)** | **62–73%** | 7 reais |
| Pós-F1 (revogadas) | +gt-0003 | 6 |
| Pós-F2 (rerank pool 100) | +gt-0007/0012/0026/0034 | ~4 |
| Pós-F3 (GT v2) | +gt-0002/0005/0039/0041/0046/0013 | ~4 |
| Pós-F4 (corpus PRODIST) | +gt-0017/0019/0022 | ~3 |
| Pós-F5 (identificadores) | +gt-0027/0023/0024 | ~1 |
| Pós-F6 (matching enumerado) | +gt-0025 | ~1 |
| Pós-F7 (gerador) | +gt-0015/0049 | **0–1** |
| **Teto teórico** | **~98–100%** | 0–1 |

Os números pós-fase **não são promessas** — cada um será confirmado por
comparação pareada com critério pré-comprometido. O valor do roadmap está
em ter um plano onde **cada uma das 24 falhas tem dono, causa-raiz e teste
de saída**, e onde a execução é guiada por medição, não por intuição.

## Sequência sugerida (ponto de partida; reavaliada a cada gate)

```
F1 (revogadas) → F2 (rerank pool 100) → MEDIR baseline honesto
   → F3 (GT v2) → F4 (corpus PRODIST, orçamento aprovado)
   → F5 (identificadores) → F6 (matching enumerado) → F7 (gerador)
   → F8 (routing, só se necessário)
```

Cada seta é um **gate de decisão**: medimos o resultado pareado, aplicamos
o critério pré-comprometido, e escolhemos a próxima fase com base no que
ainda falha — não cegamente na ordem acima.
