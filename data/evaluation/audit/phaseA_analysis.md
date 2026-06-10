# Auditoria Fase A — análise consolidada

> Auditor externo (LLM forte com web search) revisou as 24 falhas do
> baseline RAG. **23 dos 24 vereditos com confiança `high`.** Resultado:
> a hipótese do usuário (GT incompleto/desatualizado inflando falhas)
> está **parcialmente confirmada** — mas com nuance importante.

## Veredito agregado

| veredito | n | question_ids |
|---|---:|---|
| `system_partially_right` | 8 | gt-0025, gt-0026, gt-0028, gt-0029, gt-0030, gt-0034, gt-0037, gt-0049 |
| `gt_correct_system_failed` | 6 | gt-0003, gt-0007, gt-0012, gt-0023, gt-0024, gt-0027 |
| `gt_incomplete_alternative_source` | 4 | gt-0002, gt-0005, gt-0039, gt-0046 |
| `gt_outdated` | 4 | gt-0015, gt-0017, gt-0019, gt-0022 |
| `gt_question_ambiguous` | 1 | gt-0013 |
| `gt_excerpt_problematic` | 1 | gt-0041 |

## Reclassificação pelo `system_assessment` (a leitura que importa)

O veredito sozinho engana: um caso pode ser `gt_outdated` **e** o sistema
estar errado mesmo assim (gt-0015). O que importa pra recalcular usabilidade
é o `system_assessment` — se a **resposta do sistema** está factualmente
correta, independente do rótulo do GT:

| categoria | n | question_ids |
|---|---:|---|
| **Sistema factualmente correto** (falha era 100% do GT) | 6 | gt-0002, gt-0005, gt-0017, gt-0039, gt-0041, gt-0046 |
| **Sistema parcial** (defensável, com perdas) | 11 | gt-0013, gt-0019, gt-0022, gt-0025, gt-0026, gt-0028, gt-0029, gt-0030, gt-0034, gt-0037, gt-0049 |
| **Sistema realmente errado** (falha irredutível) | 7 | gt-0003, gt-0007, gt-0012, gt-0015, gt-0023, gt-0024, gt-0027 |

## Cenários de `answer_usable_rate`

Estado atual: **24/48 = 50,0%**

| cenário | regra | resultado |
|---|---|---|
| **A — conservador** | só os 6 factualmente corretos viram usable | 30/48 = **62,5%** (+6) |
| **B — intermediário** | corretos + metade dos parciais | 35/48 = **72,9%** (+11) |
| **C — otimista** | corretos + todos os parciais | 41/48 = **85,4%** (+17) |

- **Piso de falha real do sistema**: 7 perguntas (14,6%) — irredutível
  sem mexer no retrieval/geração.
- **Teto realista de usabilidade**: 41/48 = 85,4%.

**Conclusão central:** a métrica atual de 50% subestima o sistema. O número
honesto está entre **62,5% (conservador)** e **72,9% (intermediário)**. A
hipótese do usuário estava certa — boa parte das "falhas" é ruído de GT,
não falha de sistema. Mas **7 falhas são reais** e não somem com correção
de GT.

## Ações de correção de GT (10 perguntas)

### `add_alternative_source` (4) — schema `any_of`, issue #6 do SUMMARY
- **gt-0002**: + PRORET Submódulo 6.8 v1.10C (bandeiras tarifárias)
- **gt-0005**: + REN 1.059/2023 (ato alterador, fonte despachável)
- **gt-0039**: + itens 2.1+ do Submódulo 2.14-RQ (mesmo doc, chunks complementares)
- **gt-0046**: + chunks complementares do mesmo manual de transmissão

### `replace_outdated` (4) — PRODIST migrou pra REN 956/2021
- **gt-0015**: PRODIST Módulo 1 v0 → v11
- **gt-0017**: PRODIST Módulo 3 v0 → v9
- **gt-0019**: PRODIST Módulo 7 v0 → v6
- **gt-0022**: PRODIST Módulo 10 v0 → v4

⚠️ Atenção: em **gt-0015** o auditor diz que a fonte está desatualizada,
mas a **resposta do sistema continua errada** (confundiu glossário com
fundamentos legais). Corrigir o GT aqui **não** salva a pergunta.

### `fix_excerpt` (1)
- **gt-0041**: Submódulo 8.3-PR lista 11 parcelas (a–k); GT só tem 3.
  Sistema estava mais completo que o GT.

### `clarify_question` (1)
- **gt-0013**: REN 1095/2024 tem duas dimensões (nº da UC vs CPF/CNPJ);
  pergunta ambígua.

## Padrão sistêmico descoberto: PRODIST desatualizado em massa

Os 4 `gt_outdated` são **todos PRODIST** apontando pra versão `v0`
(`aren2008345`, de 2008) quando a vigente é `aren2021956` (REN 956/2021).
Isso sugere um **erro sistemático na construção do GT**: as URLs do PRODIST
foram coletadas de uma versão antiga. **Vale auditar os PRODIST que
PASSARAM também** — podem ter passado por coincidência de conteúdo estável
entre versões, ou podem ter o mesmo defeito latente.

## Padrão nas falhas reais (7): confusão entre submódulos/atos vizinhos

- gt-0023, gt-0024: somam **RI** indevidamente à Parcela A (puxaram Submódulo 2.1**A** em vez de 2.1)
- gt-0027: respondeu objetivo do Submódulo 2.1 quando perguntado 2.4
- gt-0007: confundiu REN 905/2020 (transmissão) com PRORET/Conta-Covid
- gt-0012: não recuperou REN 1032/2022 (PMO/CMO/PLD) e disse "sem base"
- gt-0003: usou REN 414 (revogada) em vez de REN 1000/2021
- gt-0015: confundiu glossário PRODIST com fundamentos legais

**Diagnóstico**: o retrieval confunde documentos com identificadores
quase idênticos (2.1 vs 2.1A; 2.1 vs 2.4; 905 vs vizinhos). Isso é
**exatamente** o tipo de falha que a Query Expansion da Fase 2 tentou
resolver e o chunking da Fase 3 pode agravar. Reforça priorizar
discriminação de identificadores documentais no retrieval.

## Próximos passos recomendados

1. **Fase B (calibração)**: rodar a amostra de 8 perguntas que passaram
   pra estimar falsos positivos. Especialmente útil agora que sabemos do
   defeito sistemático do PRODIST — se alguma das que passaram for PRODIST,
   checar se passou por sorte.
2. **GT v2**: aplicar as 10 correções. Priorizar os 4 `replace_outdated`
   do PRODIST (defeito sistemático, fácil de corrigir em lote) e os 4
   `add_alternative_source` (schema `any_of`).
3. **Re-rodar benchmark** com GT v2 → medir o `answer_usable_rate` real
   (esperado: ~62–73%).
4. **Atacar as 7 falhas reais**: são problema de discriminação de
   identificador no retrieval — alinhado com Fase 3 (chunking) e possível
   QE direcionada.
