# GT v2 — plano de correção (revisado após inspeção do corpus)

> **Descoberta que muda o escopo:** ao cruzar as sugestões do auditor com
> o corpus indexado (`data/documentos_corpus.csv`) e o validador
> (`src/evaluation/ground_truth.py`), 4 das 10 "correções de GT" são na
> verdade **correções de corpus** (mais caras), 1 exige mudar o validador,
> e só 3 são seguras de aplicar diretamente no JSONL.

## A descoberta central: corpus desatualizado, não (só) o GT

O auditor externo marcou 4 perguntas PRODIST como `gt_outdated` porque a
URL do GT aponta pra versão de 2008 (`aren2008345...v0`) e a internet tem
a vigente de 2021 (`aren2021956`). **Mas o corpus indexado também é v0:**

```
prodist-modulo-01  url_original = .../aren2008345_Prodist_modulo_1_v0.pdf
prodist-modulo-03  url_original = .../aren2008345_Prodist_modulo_3_v0.pdf
prodist-modulo-07  url_original = .../aren2008345_Prodist_modulo_7_v0.pdf
prodist-modulo-10  url_original = .../aren2016730_Prodist_modulo_10_v0.pdf
```

GT e corpus **concordam** (ambos v0). O auditor só viu o GT vs internet.
Trocar só a URL do GT pra 2021:
1. **Quebra a validação** — `_validate_source` exige URL ∈ corpus (linha 446)
2. **Não muda o retrieval** — o índice continua v0

→ Corrigir de verdade = re-baixar PRODIST 2021 + re-extrair + **re-indexar
vectorstore (~US$3-8 OpenAI)** + atualizar corpus CSV. É Fase 3/4, não GT v2.

## Três restrições do validador (`ground_truth.py`)

1. **URL da fonte** ∈ {`url_original`, `url_consolidado`} do corpus (linha 443-449)
2. **`support_excerpt`** com cobertura ≥ 0.70 no texto do corpus, se
   `corpus_supported` (linha 451-460)
3. **tipo/subtipo uniforme** entre todas as fontes de uma pergunta vs o
   documento (linha 433-442) — bloqueia fonte alternativa de tipo diferente

## Reclassificação das 10 correções

| qid | sugestão | classe | ação |
|---|---|---|---|
| gt-0005 | + REN 1059/2023 | ✅ segura | `ren-2023-1059` no corpus, tipo ren, URL ok |
| gt-0039 | + 2º trecho mesmo doc | ✅ segura | mesmo `proc-rede-2-14-rq` |
| gt-0046 | + chunks mesmo manual | ✅ segura | mesmo manual de transmissão |
| gt-0002 | + PRORET 6.8 | ⚠️ validador | PRORET≠REN viola tipo uniforme |
| gt-0015 | PRODIST→2021 | ❌ corpus | rebuild; +sistema errou conteúdo |
| gt-0017 | PRODIST→2021 | ❌ corpus | rebuild vectorstore |
| gt-0019 | PRODIST→2021 | ❌ corpus | rebuild vectorstore |
| gt-0022 | PRODIST→2021 | ❌ corpus | rebuild vectorstore |
| gt-0041 | excerpt 3→11 parcelas | 🟡 depende | só se corpus tiver 11 parcelas |
| gt-0013 | reformular pergunta | 🟡 delicado | muda texto → quebra comparabilidade |

## Ponto conceitual importante

**Editar o GT NÃO é o que estabelece o número honesto de 62-73%.** Esse
número já foi provado pela auditoria (`AUDIT_CONCLUSION.md`),
independentemente de tocar no JSONL. Editar o GT serve para:
- (a) runs **futuros** refletirem o número honesto automaticamente;
- (b) corrigir defeitos reais p/ quem mais usar o benchmark.

A análise intelectual já está completa. O GT v2 é higiene de dados, não
descoberta.

## Pré-requisito técnico para as 3 correções seguras

Mesmo as 3 seguras precisam de um `support_excerpt` real extraído do
**texto** do documento (não está no CSV de metadados — está no Hub via
`carregar_corpus_hub`). Sem o texto, qualquer excerpt escrito à mão
arrisca falhar a validação de cobertura ≥ 0.70.

Fluxo correto para aplicar (quando decidido):
1. `carregar_corpus_hub()` → DataFrame com `texto_bruto`
2. Para cada correção segura, extrair trecho literal do `texto_bruto` do doc
3. Montar nova linha do JSONL com a fonte adicional
4. `validate_ground_truth(rows, corpus_df=corpus)` → tem que passar limpo
5. Bump de versão + `publish_ground_truth(..., version="v2")`
6. Re-rodar benchmark contra GT v2

## Recomendação de escopo

Três blocos, em ordem de ROI decrescente:

- **Bloco 1 (barato, alto valor de higiene):** aplicar gt-0005, gt-0039,
  gt-0046. Requer download do corpus do Hub + extração de excerpts +
  republicação v2. Sem custo OpenAI.
- **Bloco 2 (médio):** relaxar o validador para aceitar fontes
  cross-tipo (`any_of` multi-tipo) → destrava gt-0002 e abre espaço para
  fontes alternativas de tipos diferentes no futuro. Mudança de código +
  testes.
- **Bloco 3 (caro, separado):** rebuild do corpus PRODIST 2008→2021
  (gt-0015/17/19/22). Custa rebuild de vectorstore. Decisão de orçamento.
  Tratar como issue própria, fora do GT v2.

gt-0041 e gt-0013 ficam para revisão manual posterior (dependem de
inspeção do texto / decisão sobre comparabilidade).
