# Fase 2 — Query Expansion: relatório

**Status:** concluída. Veredito (regra pré-comprometida): **`keep_baseline`**
em ambos os pares. Código de QE permanece no repositório como infraestrutura
inativa por default (`query_expansion=False`); artefatos oficiais
(`per_question.json`, `results.csv`, `failure_analysis.*`,
`rerank_pairing.*`) restaurados ao estado pré-QE.

## Objetivo

Atacar as 11 falhas de retrieval do baseline (7 `retrieval_document_failure`
+ 4 `retrieval_passage_failure`), em particular os 3 casos identificados
pelo SUMMARY como gap de vocabulário (gt-0005, gt-0025, gt-0027),
adicionando um rewriter LLM antes do retrieval que incorpora termos
técnicos discriminantes do domínio ANEEL. **O gerador continua vendo a
pergunta original.**

## Arquitetura implementada

- `src/rag/query_expander.py`: `QueryExpander` com `expand(query)` →
  `{expanded_query, added_terms, status, error}`. Status:
  `ok | skipped_no_key | error | identifier_drift | skipped_missing_openai`.
  Passthrough seguro em qualquer status != `ok`.
- Validação anti-drift de identificador documental por regex
  (`REN N/AAAA`, `PRORET Submódulo X.Y`, `PRODIST Módulo N`, `Lei N/AAAA`,
  `Despacho N/AAAA`). Identificadores presentes na original devem aparecer
  na expandida; senão, passthrough com `status=identifier_drift`.
- `src/rag/naive.py` (`NaiveRAG`): recebe `query_expander` opcional;
  retriever vê query expandida, generator vê query original; persiste
  `query`, `expanded_query`, `query_expansion_status`,
  `query_expansion_error` na response.
- `src/evaluation/benchmark.py`: `StoreConfig.query_expansion: bool`;
  `build_rag_baseline_configs(query_expansion=False)` gera 2 ou 4 configs
  (cartesiano rerank × QE); `_default_rag_factory` instancia
  `QueryExpander` quando flag ativa; `evaluate_question_rag` persiste
  os campos de QE no per_question.
- `scripts/run_benchmark.py`: flags `--query-expansion` e
  `--query-expansion-model`; emite `query_expansion_pairing.{json,md}`
  automaticamente quando há 4 configs.
- `scripts/analyze_query_expansion_pairing.py`: pareamento independente
  para os dois pares (sem rerank e com rerank).
- 8 testes em `tests/test_query_expander.py` + 1 em `tests/test_rag.py`.
  Total: 175 testes verdes; `make lint` limpo.

## Critério de decisão (pré-comprometido)

> Promover `--query-expansion` a default SE
> `saved_by_qe >= 2 * broken_by_qe` E
> `delta_retrieval_failures <= 0` (soma `document_failure + passage_failure`
> não pode piorar) E
> `delta_doc_failure <= 0`. Caso contrário, `keep_baseline`.

## Resultados pareados

### Par 1 — efeito de QE sobre baseline puro (rerank=False)

| Bucket | Count |
|---|---:|
| `saved_by_qe` | 4 |
| `broken_by_qe` | 6 |
| `stable_pass` | 20 |
| `stable_fail_same_type` | 13 |
| `stable_fail_changed_type` | 5 |

- `answer_usable_rate`: 0.542 → 0.500 (**−2 perguntas**)
- `delta_retrieval_failures`: **+2** (piorou)
- `delta_doc_failure`: **+1** (piorou)
- `qe_status_counts`: `{ok: 48}` — todas as expansões bem-formadas,
  nenhum drift, nenhum erro
- Veredito: **`keep_baseline`**
- Razões: `saved=4 < 2*broken=12`; `delta_retrieval=+2`; `delta_doc=+1`

### Par 2 — efeito de QE sobre baseline+rerank

| Bucket | Count |
|---|---:|
| `saved_by_qe` | 3 |
| `broken_by_qe` | 5 |
| `stable_pass` | 22 |
| `stable_fail_same_type` | 14 |
| `stable_fail_changed_type` | 4 |

- `answer_usable_rate`: 0.562 → 0.521 (**−2 perguntas**)
- `delta_retrieval_failures`: **+2** (piorou)
- `delta_doc_failure`: 0 (neutro)
- Veredito: **`keep_baseline`**
- Razões: `saved=3 < 2*broken=10`; `delta_retrieval=+2`

## Salvas e quebradas — análise qualitativa

### Quem a QE salvou (par 1)

| qid | mudança | mecanismo |
|---|---|---|
| `gt-0003` | `citation_and_answer_failure → usable` | gerador montou resposta melhor com contextos ligeiramente diferentes |
| `gt-0013` | `answer_quality_failure → usable` | mesmo padrão |
| `gt-0023` | `citation_and_answer_failure → usable` | mesmo padrão |
| `gt-0034` | `retrieval_passage_failure → usable` | **único caso onde QE atacou o alvo original** — expansão "regras de conexão" trouxe trecho específico |

3 das 4 salvas são em casos de **falha de gerador**, não de retrieval —
QE alterou o pool de contextos como efeito colateral, ajudando o gerador.
Apenas `gt-0034` se encaixa no caso de uso intencional da QE.

### Quem a QE quebrou (par 1) — três mecanismos distintos

**Tipo A — QE expulsou o documento certo (doc_recall 1 → 0):**
- `gt-0010`, `gt-0012`: termos genéricos adicionados ("governança",
  "remuneração do capital") puxaram outros documentos. Notavelmente,
  `gt-0012` era das poucas perguntas que o rerank salvava no run anterior
  — QE+rerank a quebrou.

**Tipo B — doc certo continua, mas trecho mudou (doc=1, recall 1 → 0):**
- `gt-0004`, `gt-0040`: termos adicionados (e.g. "medição, conexão à
  rede, compensação") competiram com o excerpt literal esperado, fazendo
  o retriever priorizar outros chunks do mesmo doc.

**Tipo C — contexto perfeito (recall=1), mas resposta/citação pioraram:**
- `gt-0018`, `gt-0036`, `gt-0037`, `gt-0039`, `gt-0048`: o retriever
  pegou um conjunto diferente de chunks do mesmo doc; o gerador, vendo
  esse novo pool, montou citação ou resposta pior. Sintoma "indireto"
  de QE sobre o gerador.

### Os 3 casos do SUMMARY foram **NÃO salvos**

- `gt-0005`, `gt-0025`, `gt-0027`: continuam falhando. O prompt
  `GENERIC` não inferiu os termos discriminantes específicos
  ("custo de capital", "taxa regulatória de remuneração de capital")
  necessários para esses casos.

Isso confirma experimentalmente o achado do experimento 1.3-alt
(SUMMARY, linhas 159-172): com oracle manual incluindo os termos
exatos, gt-0027 sobe de 0 → 1.0 em todas as configs. Sem oracle,
nenhum prompt LLM testado até agora consegue chegar lá.

## Diagnóstico

QE com prompt genérico **adiciona ruído mais do que sinal**: amplia o
campo semântico da query com termos do domínio amplo, que **competem**
com a especificidade do documento certo em vez de filtrar pra ele.
O resultado é uma reordenação que ocasionalmente ajuda (4-3 perguntas)
mas mais frequentemente atrapalha (6-5 perguntas).

Status do rewriter foi 100% `ok` — não é problema técnico do código
ou do drift de identificador. É problema **semântico do prompt**:
inferir termos discriminantes sem ver o documento exige conhecimento
domínio-específico que o LLM genérico não tem.

## Ações aplicadas

- **Veredito respeitado**: artefatos oficiais
  (`per_question.json`, `results.csv`, `failure_analysis.*`,
  `rerank_pairing.*`) restaurados ao estado pré-QE.
- **Artefatos do run com QE preservados** com sufixo `_qe` para
  auditoria.
- **Código de QE permanece no repositório** como infraestrutura
  disponível mas inativa por default. `make benchmark-rag` continua
  gerando 2 configs (baseline + rerank), sem QE, exatamente como antes.
- **`make test` (175 passando) e `make lint` (limpo) confirmam estado
  estável**.

## Lições

1. **A direção de QE não é descartável, mas o prompt GENERIC não funciona
   pra este corpus.** Precisaria fornecer dicas direcionadas (e.g., um
   índice de termos técnicos pré-construído por documento, ou um
   classificador que decide se a pergunta é candidata a QE).
2. **QE indiscriminada degrada perguntas que já passavam**: 11 perguntas
   regridem somando os dois pares. Sem um sinalizador de "esta pergunta
   se beneficia de QE", aplicar globalmente é prejudicial.
3. **A regra pré-comprometida valeu de novo**: o `answer_usable_rate`
   caiu em ambos os pares; sem o critério estrito a interpretação fácil
   seria "QE piorou, vamos descartar a ideia inteira" — mas o
   diagnóstico pareado mostra que ela **funciona em 4 perguntas
   específicas**. Esse aprendizado fica registrado.
4. **Custo experimental aceitável**: ~192 chamadas LLM, ~US$0,30.
   A infraestrutura é reaproveitável para experimentos futuros (por
   exemplo: QE só em perguntas sem identificador documental explícito,
   ou QE com prompt enxuto de retrieval-aware).

## Próximo passo

Avançar para **Fase 3 — fix do chunking article-aware (H12)**. O
SUMMARY confirmou que o regex `ARTICLE_RE` fragmenta documentos
markdown em chunks tiny (mediana ~22 palavras). Isso afeta o
hierarchical e o article-aware. A intervenção é estrutural mas
mensurável; custo de rebuild OpenAI documentado (~US$3-8).
