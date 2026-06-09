# Fase 1 — Prompt engineering nas 13 falhas do Mundo 2

**Status:** concluída. Veredito: `keep_v1`. Prompt revertido ao original.

## Objetivo

Atacar as 13 falhas do baseline RAG cuja causa raiz era no gerador, não no
retrieval. Distribuição original:

| tipo | quantas |
|---|---:|
| `citation_and_answer_failure` | 7 |
| `citation_failure` | 3 |
| `answer_quality_failure` | 3 |

## Hipótese

Três padrões de erro do LLM eram fixáveis por instruções mais explícitas no
`SYSTEM_PROMPT`:

- **A. Citou doc errado tendo o certo no contexto** (LLM viu texto similar
  em outro doc) — alvo: `gt-0003`, `gt-0013`, `gt-0028`.
- **B. Respondeu além do pedido** (adicionou detalhes que sujam a comparação) —
  alvo: `gt-0023`, `gt-0024`, `gt-0049`.
- **C. Citou blocos demais** (cit ~0.33 por incluir auxiliares) — alvo:
  `gt-0019`, `gt-0022`, `gt-0039`, `gt-0046`.

## Intervenção (prompt v2)

Substituí o `SYSTEM_PROMPT` de 4 linhas por uma versão com 4 regras
numeradas: priorização de documento (A), concisão (B), citação parcimoniosa
(C), e mantendo a regra antiga de "sem base, diga".

Artefatos preservados em:

- `per_question_promptv2.json`
- `results_promptv2.csv`
- `failure_analysis_promptv2.{json,md}`
- `rerank_pairing_promptv2.{json,md}`

## Critério de decisão (pré-comprometido)

> Promover prompt v2 SE `saved_by_prompt_v2 >= 2 * broken_by_prompt_v2`
> E `delta_citation_failures <= 0` E `delta_answer_failures <= 0`.

Comprometido antes de ver os números, igual ao pareamento de rerank.

## Resultado pareado

| Bucket | Count |
|---|---:|
| `saved_by_prompt_v2` | 4 |
| `broken_by_prompt_v2` | 3 |
| `stable_pass` | 21 |
| `stable_fail_same_type` | 17 |
| `stable_fail_changed_type` | 3 |

`answer_usable_rate`: v1 0.500 → v2 0.521 (`net_delta=+1`)
`citation_failures` agregadas: `delta=-2`
`answer_failures` agregadas: `delta=-2`

### Salvas pelo prompt v2 (4)

- `gt-0019`: `citation_failure → usable` ✓ (padrão C atingido)
- `gt-0039`: `citation_failure → usable` ✓ (padrão C)
- `gt-0046`: `citation_failure → usable` ✓ (padrão C)
- `gt-0049`: `answer_quality_failure → usable` ✓ (padrão B)

### Quebradas pelo prompt v2 (3)

Todas perderam citação correta por excesso de zelo na regra "citação
parcimoniosa":

- `gt-0004`: pergunta sobre REN 1000. v1 citou REN 1000 + REN 1095 (cit=0.5).
  v2 cortou para 1 citação e ficou com REN 1095 (cit=0).
- `gt-0008`: pergunta sobre REN 1003. v1 citou 2 chunks do mesmo doc certo
  (cit=0.5); v2 cortou e ficou com o chunk que não casa com o excerpt
  esperado.
- `gt-0018`: pergunta sobre PRODIST Módulo 5. v1 citou Módulo 1 + Módulo 5
  (cit=0.5). v2 cortou e ficou com Módulo 1.

### Mudanças diagnósticas (3)

- `gt-0022`: `citation_and_answer → answer_quality` (citation passou, answer
  ainda falha)
- `gt-0024`: `citation_and_answer → citation_failure` (lateral)
- `gt-0028`: `citation_and_answer → answer_quality` (citation passou)

## Veredito

`keep_v1`. Razão: `saved=4 < 2*broken=6`. A regra de promoção falhou pelo
ratio. Os deltas agregados de citação e resposta vieram negativos (=
melhoras), mas o trade-off por pergunta não foi defensável.

## Por que falhou

A regra 1 ("priorize doc com identificador") **não foi seguida pelo LLM
na hora de escolher qual citação manter** quando a regra 3 ("citação
parcimoniosa") o forçou a cortar. Diagnóstico: o LLM cortou sem priorizar
o documento mencionado na pergunta, ficando com citação aleatória.

Isso aparece de forma cristalina nas 3 quebradas: em todas, a citação que
sobrou no v2 é a que **não** casa com o documento esperado, embora o doc
certo estivesse no contexto e fosse explicitamente mencionado na pergunta.

## Ações aplicadas

- `SYSTEM_PROMPT` revertido para a versão original em `src/rag/generator.py`.
- Artefatos v1 restaurados como oficiais (`per_question.json`, `results.csv`,
  etc.).
- Artefatos v2 preservados com sufixo `_promptv2` para auditoria futura.
- `make test` (166 passaram) e `make lint` (limpo) confirmam estado estável.

## Lições e direções futuras

1. **A direção é razoável, mas a regra precisa ser mais cirúrgica.** Um
   prompt v3 poderia tornar a regra 1 OBRIGATÓRIA (não apenas preferencial)
   e afrouxar a regra 3. Mas custo de mais uma rodada de LLM contra ganho
   incerto.

2. **3 das 13 falhas têm causa em "chunk errado dentro do doc certo"**
   (`gt-0015`, `gt-0037`, `gt-0041`). Essas não eram fixáveis por prompt —
   dependem do retriever ranquear o chunk certo no top-k. Reforça a
   prioridade de Fase 2 (query expansion) e Fase 3 (chunking).

3. **Eficácia esperada de prompt engineering puro: marginal.** Mesmo num
   cenário otimista, a Fase 1 conseguiu salvar 4 perguntas (8% das 50)
   sem quebrar nenhuma seria o teto. Aqui o teto líquido foi +1, e mesmo
   esse veio acompanhado de regressões inaceitáveis.

## Próximo passo

Avançar para **Fase 2 — query expansion** sem mais iteração de prompt nesta
sessão. As perguntas com gap de vocabulário (`gt-0005`, `gt-0025`, `gt-0027`
e possivelmente outras) são candidatas naturais.
