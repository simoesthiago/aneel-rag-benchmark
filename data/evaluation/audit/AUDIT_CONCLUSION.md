# Auditoria externa do Ground Truth — conclusão consolidada (Fase A + B)

> Auditor externo (LLM forte com web search) revisou **24 falhas (Fase A)**
> + **8 aprovações (Fase B)** do baseline RAG. **31/32 vereditos com
> confiança alta ou média justificada.** Conclusão: a métrica é
> **assimetricamente confiável** e o `answer_usable_rate` real é
> **~62–73%**, não 50%.

## Veredito de uma frase

> A hipótese do usuário se confirma: **o GT estava inflando as falhas**.
> A métrica não gera falsos positivos (0/8), mas gera falsos negativos
> (10/24 "falhas" eram problema do GT, não do sistema). O número honesto
> de usabilidade é **62,5% (conservador) a 72,9% (intermediário)**, com
> **7 falhas reais irredutíveis** (14,6%).

## Fase B — calibração de falsos positivos

| métrica | resultado |
|---|---|
| Falsos positivos | **0 / 8 (0,0%)** |
| Confiança | 6 high, 2 medium |
| Veredito unânime | `system_correctly_passed` |

**Interpretação:** quando a métrica diz "passou", ela acertou em 8/8.
Pela regra estatística dos três (Rule of Three), com 0/8 o teto de taxa
real de falso positivo a 95% é ~37% — n=8 é pequeno, mas a ausência total
de FP é forte sinal de que **não estamos superestimando o sistema**.

### O teste crítico do PRODIST passou

A Fase A revelou um defeito sistemático: 4 perguntas com PRODIST apontando
pra versão de 2008 (`aren2008345`) em vez da vigente (REN 956/2021). A
pergunta era: **as PRODIST que PASSARAM passaram por sorte?**

Resposta: **não.** As 3 PRODIST da amostra B (gt-0016, gt-0018, gt-0021)
foram confirmadas corretas pelo auditor, que verificou a versão vigente
956/2021. O conteúdo desses módulos é estável entre versões, então a URL
errada do GT não gerou falso positivo. **O defeito de GT é de citação/URL,
não de conteúdo** — bom, porque é mais fácil de corrigir.

## Quadro unificado das 24 falhas (Fase A)

| balde (pelo `system_assessment`) | n | question_ids |
|---|---:|---|
| 🟢 Sistema certo, GT errado | 6 | gt-0002, gt-0005, gt-0017, gt-0039, gt-0041, gt-0046 |
| 🟡 Sistema parcial (defensável) | 11 | gt-0013, gt-0019, gt-0022, gt-0025, gt-0026, gt-0028, gt-0029, gt-0030, gt-0034, gt-0037, gt-0049 |
| 🔴 Sistema realmente errado | 7 | gt-0003, gt-0007, gt-0012, gt-0015, gt-0023, gt-0024, gt-0027 |

## answer_usable_rate — corrigido

Hoje: **24/48 = 50,0%**

| cenário | resultado |
|---|---|
| A — conservador (só os 6 verdes) | **30/48 = 62,5%** |
| B — intermediário (verdes + ½ parciais) | **35/48 = 72,9%** |
| C — otimista (verdes + parciais) | 41/48 = 85,4% |
| Piso de falha real (irredutível) | 7/48 = 14,6% |

## Correções de GT a aplicar (GT v2)

### Prioridade 1 — `replace_outdated` (lote PRODIST, defeito sistemático)
| qid | de | para |
|---|---|---|
| gt-0015 | PRODIST Mód 1 v0 | v11 (956/2021) |
| gt-0017 | PRODIST Mód 3 v0 | v9 (956/2021) |
| gt-0019 | PRODIST Mód 7 v0 | v6 (956/2021) |
| gt-0022 | PRODIST Mód 10 v0 | v4 (956/2021) |

⚠️ gt-0015: corrigir a URL **não** salva a pergunta — o sistema errou o
conteúdo (confundiu glossário com fundamentos legais). Continua 🔴.

### Prioridade 2 — `add_alternative_source` (schema `any_of`, issue #6)
| qid | adicionar |
|---|---|
| gt-0002 | PRORET Submódulo 6.8 v1.10C |
| gt-0005 | REN 1.059/2023 (ato alterador) |
| gt-0039 | itens 2.1+ do Submódulo 2.14-RQ (mesmo doc) |
| gt-0046 | chunks complementares do manual de transmissão |

### Prioridade 3 — pontuais
- **gt-0041** `fix_excerpt`: Submódulo 8.3-PR tem 11 parcelas (a–k), GT só 3
- **gt-0013** `clarify_question`: REN 1095/2024 tem 2 dimensões (nº UC vs CPF/CNPJ)

## As 7 falhas reais — padrão único de retrieval

Todas são **confusão entre documentos com identificadores quase idênticos**:

| qid | erro |
|---|---|
| gt-0023, gt-0024 | somaram RI à Parcela A (puxaram Submódulo 2.1**A** em vez de 2.1) |
| gt-0027 | respondeu objetivo do 2.1 quando perguntado 2.4 |
| gt-0007 | confundiu REN 905/2020 (transmissão) com PRORET/Conta-Covid |
| gt-0012 | não recuperou REN 1032/2022; disse "sem base" |
| gt-0003 | usou REN 414 (revogada) em vez de REN 1000/2021 |
| gt-0015 | confundiu glossário PRODIST com fundamentos legais |

**Diagnóstico:** o retrieval denso não distingue identificadores
documentais vizinhos. É o mesmo problema que a Query Expansion (Fase 2)
tentou e falhou em resolver com prompt genérico. Candidato forte pra uma
intervenção direcionada: re-ranking por identificador documental explícito
na pergunta, ou um filtro de metadados quando a pergunta cita um
submódulo/REN específico.

## Próximos passos

1. **GT v2**: aplicar as 10 correções. Começar pelo lote PRODIST (4,
   mecânico). Schema `any_of` para as 4 fontes alternativas.
2. **Re-rodar benchmark** com GT v2 → confirmar `answer_usable_rate` real
   (esperado ~62–73%).
3. **Atacar as 7 falhas reais** com foco em discriminação de identificador
   documental no retrieval (não é chunking puro — é desambiguação).
4. **Atualizar HANDOFF/SUMMARY** com o novo número honesto de usabilidade.
