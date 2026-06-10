# Fase 2 — Rerank pool 100: relatório

**Status:** concluída. Veredito (regra pré-comprometida): **`promote`** no
pareamento decisivo. Pool 100 foi promovido a default do rerank em
`build_rag_baseline_configs`.

## Objetivo

Medir, com rigor pareado, se aumentar o pool de candidatos densos do rerank
de 50 para 100 melhora o `answer_usable` no benchmark RAG completo. O
`diagnostic/SUMMARY.md` (Achado 5) já mostrara, **em retrieval puro**, que
pool 100 salva gt-0007/0012/0030/0034 (+4pp passage_recall), mas isso nunca
fora medido na resposta final (answer_usable). Causa: o benchmark RAG
instanciava o rerank com `candidates_k_override=None` → pool default (~50).

## Desenho experimental

3 configs no mesmo run (consistência interna; LLM gerador/juiz varia entre
runs, então só o pareamento interno é confiável):

- `baseline` (sem rerank)
- `rerank@50`
- `rerank@100`

Dois pareamentos por `question_id`:
- **Par 1 (decisivo):** `rerank@50` vs `rerank@100` — isola o efeito do pool.
- **Par 2 (contexto):** `baseline` vs `rerank@100` — ganho total do rerank-bom.

## Critério de decisão (pré-comprometido)

> Promover pool 100 a default SE, no Par 1: `saved >= 2*broken` E
> `delta_doc_recall >= -0.02`. Caso contrário, `keep_pool50`.

## Resultados agregados (este run)

| config | answer_usable | doc_recall@10 | passage_recall@10 |
|---|---:|---:|---:|
| baseline (sem rerank) | 0.521 (25/48) | 0.854 | 0.771 |
| rerank@50 | 0.583 (28/48) | 0.792 | 0.771 |
| **rerank@100** | **0.604 (29/48)** | 0.833 | 0.813 |

Pool 100 é o config com **maior answer_usable_rate** (+4 vs baseline, +1 vs
pool 50) e o maior passage_recall/nDCG.

## Par 1 — DECISÃO (pool50 vs pool100)

| Bucket | Count |
|---|---:|
| `saved_by_pool100` | 2 |
| `broken_by_pool100` | 1 |
| `stable_pass` | 27 |
| `stable_fail_same_type` | 14 |
| `stable_fail_changed_type` | 4 |

- **Salvas:** gt-0001 (answer_quality → usable), **gt-0007**
  (retrieval_document → usable, *a falha-alvo central*).
- **Quebrada:** gt-0047 (usable → answer_quality).
- `delta_doc_recall`: **+0.042**
- Regra: `saved=2 >= 2*broken=2` ✓ E `delta_doc_recall=+0.042 >= -0.02` ✓
- Veredito: **`promote`**

## Par 2 — CONTEXTO (baseline vs pool100)

| Bucket | Count |
|---|---:|
| `saved_by_pool100` | 6 |
| `broken_by_pool100` | 2 |
| `stable_pass` | 23 |
| `stable_fail_same_type` | 9 |
| `stable_fail_changed_type` | 8 |

- **Salvas (6):** gt-0003, gt-0007, gt-0012, gt-0034, gt-0039, gt-0046.
- **Quebradas (2):** gt-0028, gt-0047.
- `delta_doc_recall`: **-0.021** → tecnicamente reprovaria o critério (por
  0.001), refletindo o trade-off conhecido do rerank (promove alguns chunks
  de documentos errados). **Este par é informativo, não decisivo.**

## Avaliação honesta

1. **A regra pré-comprometida foi respeitada:** o Par 1 (decisivo) deu
   `promote`. Mas passou **no limite exato** (`saved=2 >= 2*broken=2`,
   margem zero) — sinal positivo, porém modesto.
2. **Ganho de pool 100 sobre pool 50 é marginal:** +1 pergunta líquida
   (salvou gt-0007, quebrou gt-0047 — net +1 após gt-0001). O grosso do
   ganho do rerank vem de tê-lo ativo (pool 50 já dá +3 sobre baseline).
3. **Falha-alvo central confirmada:** gt-0007 (rank profundo) só é salva com
   pool 100, validando empiricamente a hipótese do SUMMARY. gt-0026
   (também alvo) **não** foi salva por nenhum pool — continua
   `retrieval_document_failure`.
4. **3 das 7 falhas reais da auditoria caem com rerank@100:** gt-0003,
   gt-0007, gt-0012 viram `usable`. gt-0023/gt-0024 melhoram parcialmente
   (`citation_and_answer` → `citation_failure`: resposta correta, só a
   citação falha). Permanecem duras: gt-0015, gt-0027.
5. **Trade-off de doc_recall** aparece no Par 2 (-0.021). Não afeta a
   decisão (Par 1 é decisivo e tem +0.042), mas fica registrado: o rerank
   ocasionalmente promove documentos errados.

## Decisão aplicada

- **Pool 100 promovido a default do rerank** em
  `build_rag_baseline_configs` (`candidates_k_override=100`). Próximos
  `make benchmark-rag` usam pool 100 automaticamente.
- Run de decisão preservado em `per_question_f2_pool.json` (3 configs).
- Teste trava o novo default
  (`test_build_rag_baseline_configs_limita_escopo_a_baseline_e_rerank`).

## Limitações e próximos passos

- **n pequeno + margem mínima:** o veredito é `promote`, mas o ganho
  incremental sobre pool 50 é de 1 pergunta. Não é uma vitória dramática.
- **gt-0026 e gt-0027** (retrieval) seguem falhando → candidatas à F5
  (discriminação de identificadores) e, no caso de gt-0029/0030, à
  avaliação de pool 200+ (F2†), só se justificável.
- **gt-0003 já caiu aqui** (pelo rerank), antes da F1 (filtrar revogadas).
  A F1 ainda vale por reduzir ruído global e por estabilidade entre runs.
