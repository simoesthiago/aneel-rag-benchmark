# Auditoria externa do Ground Truth — passo a passo

Auditoria em duas fases, executada por um LLM externo forte (Claude Opus 4
com web search, GPT-5 com browsing, ou Gemini Ultra com web grounding).

- **Fase A** — auditar as 24 falhas do RAG: testar a hipótese de que o GT
  está incompleto/incorreto e está inflando o número de falhas.
- **Fase B** — auditar uma amostra de 8 das 24 perguntas que passaram:
  calibrar a métrica, detectar falsos positivos.

## Arquivos neste diretório

| arquivo | tipo | uso |
|---|---|---|
| `gt_audit_prompt.md` | prompt | **Fase A**, colar no chat |
| `gt_audit_input.json` | dados | **Fase A**, anexar no chat (24 casos) |
| `gt_audit_input.md` | dados (legível) | **Fase A** alternativa, se o modelo não aceitar JSON anexado |
| `gt_audit_passing_prompt.md` | prompt | **Fase B**, colar no chat |
| `gt_audit_passing_sample.json` | dados | **Fase B**, anexar no chat (8 casos) |
| `ground_truth_full.csv` | contexto lateral | **anexar em ambas as fases**, referência cruzada |

---

## Passo a passo — Fase A (faça primeiro)

1. **Abre um chat novo** em [claude.ai](https://claude.ai) com **Claude
   Opus 4** selecionado, ou em ChatGPT com **GPT-5** + browsing ativado.
2. **Anexa dois arquivos** ao chat:
   - `gt_audit_input.json`
   - `ground_truth_full.csv`
3. **Cola como primeira mensagem** o conteúdo completo de
   `gt_audit_prompt.md` (todo o arquivo, do `# Prompt` até o final).
4. **Espera o output.** O modelo vai devolver um array JSON com 24 entradas.
5. **Salva o output** como `data/evaluation/audit/gt_audit_phaseA_output.json`.
6. **Cola o output aqui no chat com o Claude Code** — eu processo,
   gero estatísticas e cruzo com o estado atual do projeto.

## Passo a passo — Fase B (faça depois da A)

1. **Abre OUTRO chat novo** (não reaproveite o da Fase A — contextos
   diferentes evitam contaminação de viés).
2. **Anexa dois arquivos**:
   - `gt_audit_passing_sample.json`
   - `ground_truth_full.csv`
3. **Cola como primeira mensagem** o conteúdo de `gt_audit_passing_prompt.md`.
4. **Espera o output.** Array JSON com 8 entradas.
5. **Salva** como `data/evaluation/audit/gt_audit_phaseB_output.json`.
6. **Cola aqui no Claude Code.**

---

## O que vou fazer depois com os outputs

Quando você colar os dois outputs:

1. **Validar JSON** das duas fases.
2. **Cruzar Fase A** com o estado atual:
   - Quais das 24 falhas o auditor considerou falha real do sistema
     (`gt_correct_system_failed`) → continuam sendo problema do RAG.
   - Quais foram marcadas como `gt_incomplete_alternative_source` → viram
     candidatas a adicionar fontes ao GT (formato `any_of`, issue #6 do
     SUMMARY).
   - Quais como `gt_outdated` → precisam atualização da fonte.
   - Quais como `gt_excerpt_problematic` → precisam revisão do excerpt.
3. **Cruzar Fase B** com Fase A:
   - Se Fase B retornar **0–1 falsos positivos** em 8 → a métrica é
     confiável, podemos confiar nos números atuais.
   - Se Fase B retornar **2+ falsos positivos** → a métrica está
     superestimando o sistema; vale uma amostra maior antes de decisões
     estruturais.
4. **Recalcular `answer_usable_rate`** num cenário hipotético "aplicando
   as correções do auditor" para ver quanto realmente é falha do sistema
   e quanto é ruído do GT.
5. **Priorizar a próxima fase**: se a maioria das falhas vira problema do
   GT → fase de enriquecimento do GT. Se a maioria continua sendo falha
   real → fase 3 (fix do chunking).

---

## Por que duas fases separadas em chats separados

- **Vieses opostos**: na Fase A o default é "GT pode estar errado, prove
  o contrário". Na Fase B o default é "métrica acertou, prove que falhou".
  Misturar os dois no mesmo chat contamina os defaults.
- **Custo de atenção**: o modelo entrega melhor 24 ou 8 casos do que 32.
- **Replicabilidade**: amostra fixa (seed=42) na Fase B significa que se
  você repetir a auditoria meses depois, audita as mesmas 8 perguntas.

## Sobre o `ground_truth_full.csv`

Tem as 50 perguntas do GT com seus campos planos (`question_id`,
`question`, `expected_answer`, `document_id`, `document_title`,
`citation_label`, `section_label`, `official_url`, `support_excerpt`,
`relevance`). É **referência cruzada** em ambas as fases: ajuda o auditor
a decidir se um documento citado pelo sistema (mas ausente da GT da
pergunta auditada) é fonte legítima do corpus — verificando se aparece
em outras perguntas do GT.

## Custos esperados

- **Claude Opus 4** com web search: ~24 casos × ~8 buscas = ~$5–10 na
  Fase A, ~$2–4 na Fase B. Total ~$7–14.
- **GPT-5** com browsing: similar.
- **Gemini Advanced**: incluso na assinatura mensal.

## Quando você terminar

Cola o JSON da Fase A primeiro. Eu processo e te mostro o que ele diz
antes de você rodar a Fase B — se a Fase A já for conclusiva, talvez nem
precise da B.
