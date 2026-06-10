# Alavancas de melhoria — cruzando auditoria + diagnósticos anteriores

> Resultado de cruzar a auditoria externa (Fase A/B) com os 15 diagnósticos
> anteriores (`diagnostic/SUMMARY.md`) e o estado real do corpus/código.
> Ordenado por **ROI (ganho ÷ custo)**. Duas alavancas novas de alto
> impacto que não estavam em nenhum bloco anterior.

## 🔴 ALAVANCA 1 (NOVA, maior ROI): filtrar normas revogadas do índice

**Descoberta:** **49,4% do corpus são documentos REVOGADOS** (812 de 1643).
E **0 dos 44 docs-alvo do GT são revogados** — todos vigentes ou neutros.

Ou seja: metade do índice é ruído histórico que **nunca deveria ser
recuperado**, mas compete semanticamente com as normas vigentes.

**Prova de dano direto:** gt-0003 ("Como a REN 1000/2021 define
consumidor?") — o sistema recuperou e citou a **REN 414/2010 (revogada
pela própria REN 1000)** em vez da vigente. A auditoria marcou como falha
real. A causa raiz é ingestion: a REN 414 revogada está no índice
competindo.

| | |
|---|---|
| **Ataca** | gt-0003 diretamente; reduz ruído p/ TODAS as 50 perguntas |
| **Risco** | ~zero — nenhum alvo do GT é revogado; remover só ajuda a métrica |
| **Custo** | rebuild do vectorstore filtrando `situacao != 'revogada'`. Possível sem re-embedding se o filtro for no nível de índice/metadados |
| **Tipo** | ingestion / indexação |

**Cuidado metodológico:** filtrar só os `revogada` explícitos (812).
Manter `vigente` (179) e `nan` (652, sem situação — PRODIST/PRORET/procedimentos).
Se um dia o benchmark testar perguntas históricas, reativar é trivial.

## 🟠 ALAVANCA 2 (testado, nunca acionado no RAG): rerank pool 100

**Descoberta:** o benchmark RAG instancia rerank com `candidates_k_override=None`
→ **pool default 50**. Mas o SUMMARY (Achado 5) provou que o ganho vem do
**pool 100**: +4pp passage_recall, +7pp MRR, salva gt-0007, gt-0012,
gt-0030, gt-0034. **Isso nunca foi medido no RAG completo (answer_usable).**

| | |
|---|---|
| **Ataca** | gt-0007 (rank 30) e gt-0012 (rank 32) — 2 das 7 falhas reais |
| **Trade-off** | em retrieval, quebra gt-0028 e gt-0049 (ambas "parciais" na auditoria) |
| **Custo** | ~US$0,30 + quota Cohere. Código existe; só passar `candidates_k_override=100` em `build_rag_baseline_configs` e rodar |
| **Tipo** | retrieval / configuração |

Aposta: net positivo nas falhas reais. **Precisa medir** — o trade-off de
retrieval pode não se traduzir no answer_usable.

## 🟡 ALAVANCA 3 (= Bloco 1 anterior): GT enrichment `any_of`

gt-0002, gt-0005, gt-0039, gt-0046 — fontes alternativas legítimas.
**Nuance nova:** com a Alavanca 1+2, gt-0005 pode ser resolvida por
retrieval (o SUMMARY mostra que hierarchical já dá recall 1.0 nela).
Então talvez nem precise de enriquecimento de GT para ela.

## 🟡 ALAVANCA 4: config-routing hierarchical para concept-dense

SUMMARY Achado 7: gt-0005 (Art. 2º com ~50 definições juntas) tem
recall **0 em fixed-size, 1.0 em hierarchical**. Mas hierarchical é pior
no geral (passage_recall 0.375). Solução: rotear para hierarchical só
perguntas do tipo "definição em artigo denso". Complexidade média.

## 🟢 ALAVANCA 5: query expansion direcionada (issue #10)

gt-0027 (e parcialmente gt-0023/0024) — confusão entre submódulos vizinhos
(2.1 vs 2.4, 2.1 vs 2.1A) por falta de termos discriminantes. A Fase 2
(QE genérica) **falhou** nisso. O SUMMARY mostra que com oracle manual
("custo de capital") gt-0027 vai de 0→1.0 em todas as configs. Precisa de
QE que injete termos técnicos — talvez via índice de termos por
submódulo, não prompt genérico. Complexidade média-alta.

## 🔵 ALAVANCA 6 (= Bloco 3): rebuild corpus PRODIST 2008→2021

gt-0015/17/19/22. Custo ~US$3-8. **Atenção:** gt-0015 o sistema errou o
conteúdo — rebuild não salva. As outras 3 são parciais.

## ❌ NÃO FAZER agora: fix de chunking H12

O SUMMARY confirma H12 (regex `ARTICLE_RE` fragmenta em chunks tiny,
mediana 22 palavras). **MAS** isso só afeta `article-aware` e
`hierarchical`. A config de produção é **fixed-size/markdown/flat**, que
**não sofre de H12**. Fix de H12 só importa se adotarmos a Alavanca 4
(routing hierarchical) — aí vira pré-requisito. Sozinho, é rebuild caro
sem ganho na config atual.

## Mapa: as 7 falhas reais × alavancas

| qid | causa | alavanca que ataca |
|---|---|---|
| gt-0003 | citou REN 414 revogada | **A1 (filtrar revogadas)** |
| gt-0007 | doc certo em rank 30 | **A2 (rerank pool 100)** |
| gt-0012 | doc certo em rank 32 | **A2 (rerank pool 100)** |
| gt-0027 | 2.1 vs 2.4 (vocabulário) | A5 (QE direcionada) |
| gt-0023 | 2.1 vs 2.1A (id vizinho) | A5 / boost por identificador |
| gt-0024 | 2.1 vs 2.1A (id vizinho) | A5 / boost por identificador |
| gt-0015 | conteúdo (glossário) | nenhuma barata; falha dura |

**3 das 7 falhas reais (gt-0003, gt-0007, gt-0012) são atacáveis com
A1+A2 — ambas de custo baixo e código já existente.**

## Recomendação de sequência

1. **A1 (filtrar revogadas)** — maior ROI, menor risco. Rebuild de
   índice sem re-embedding se possível.
2. **A2 (rerank pool 100 no RAG)** — barato, mede o que nunca foi medido.
3. Re-rodar benchmark com A1+A2 e GT atual → ver answer_usable_rate real.
4. Só então decidir A3–A6 com base nos números, não na intuição.

A1+A2 juntas podem mover 3 das 7 falhas reais e reduzir ruído global,
antes de qualquer mudança cara de GT ou corpus.
