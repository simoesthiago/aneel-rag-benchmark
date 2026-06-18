# Diagnóstico — fallback de chunking, markdown e a correção H12

> Por que o chunking estrutural ia mal em markdown, o que corrigimos, e por que
> o `fixed-size` ainda vence mesmo depois da correção. Fonte da seção de
> chunking do relatório.

## 1. O mecanismo (causa-raiz)

O `article-aware` tem dois caminhos: se acha cabeçalhos de artigo (`Art. N`),
corta por artigo; senão, cai num **fallback** que corta por seção/parágrafo.
O `hierarchical-child` deriva do `article-aware`, então herda o mesmo
comportamento.

A correção do regex de artigo (H12) parou de casar `Art.` espúrio em
referências cruzadas. Efeito colateral exposto: **1061 de 1643 docs markdown**
não têm cabeçalho de artigo real e caíram no fallback. O fallback antigo cortava
em **toda linha em branco** e **não reconhecia a sintaxe `##` do markdown** —
markdown é cheio de linhas em branco entre cabeçalhos, listas e tabelas, então
estilhaçava em fragmentos minúsculos. No texto puro (prosa), o mesmo fallback
era saudável (linha em branco = parágrafo real).

## 2. A correção (delimitada)

Em `src/chunking/article_aware.py`, só no caminho fallback:

- **Sectioning markdown-aware** (`MARKDOWN_HEADING_RE`): cabeçalhos `#`..`######`
  viram fronteira de seção, junto das palavras-chave regulatórias.
- **Merge de fragmentos** (`_merge_small_blocks`, `MIN_MERGE_WORDS=50`): blocos
  curtos são fundidos com vizinhos até um tamanho saudável, sem passar de 800
  palavras. O caminho-artigo não é tocado (artigos curtos são unidades legítimas).

## 3. Shape dos chunks — antes vs depois (corpus completo)

Para não misturar escopos: o "antes" desta tabela isola o efeito do fallback
antigo depois da correção do regex de artigo. A auditoria H12 inicial das stores
v1 publicadas registrava outro denominador (`article-aware` markdown: 84.653
chunks, p50 21, 61,1% <30). Aqui a comparação mede o que muda quando o fallback
passa a respeitar cabeçalhos markdown e fundir fragmentos curtos.

| | antes (fallback antigo) | depois (markdown-aware + merge) |
|---|---|---|
| markdown `article-aware` — nº chunks | 162.651 | **22.372** |
| markdown `article-aware` — mediana palavras | 16 | **158** |
| markdown `article-aware` — % < 30 palavras | 70% | **2,3%** |
| texto `article-aware` — mediana / %<30 | 85 / ~11% | 136 / 7,8% (sem regressão) |

## 4. Impacto em retrieval — v1 → v2 (large, +rerank@100, GT retrieval-50-v2)

| config | recall | doc_recall | nDCG |
|---|---|---|---|
| `article-aware` markdown | 0.521 → **0.812** | 0.812 → 0.938 | 0.372 → 0.637 |
| `article-aware` texto | 0.667 → 0.792 | 0.833 → 0.896 | 0.526 → 0.627 |
| `hierarchical-child` markdown | 0.479 → **0.833** | 0.792 → 0.917 | 0.361 → 0.660 |
| `hierarchical-child` texto | 0.604 → 0.771 | 0.854 → 0.896 | 0.480 → 0.613 |

Ganho de até **+35 pp de recall**. Depois da correção, o **markdown passa a
vencer o texto** nas estratégias estruturais — o chunking estrutural finalmente
usa a estrutura que o markdown preserva.

## 5. Conclusão

Mesmo no seu melhor caso honesto, as estratégias estruturais **continuam atrás
da família `fixed-size`**. No modelo large com rerank, `fixed-size·markdown`
tem o maior `doc_recall` (recall 0.958 / doc_recall 0.979 / nDCG 0.867), e
`fixed-size·texto` tem o maior nDCG (recall 0.958 / doc_recall 0.958 /
nDCG 0.872). A melhor estrutural fica em recall 0.833 / doc_recall 0.917 /
nDCG ~0.66. A vitória da janela fixa é **robusta**, não artefato de uma
concorrente sabotada: janela fixa com overlap evita o problema de detecção de
estrutura em corpus regulatório heterogêneo.

**Trabalho futuro aberto a terceiros:** um splitter markdown ainda mais rico
(tabelas, listas aninhadas, code blocks) poderia estreitar mais a distância —
mas a evidência sugere retorno decrescente, pois tornar o chunking estrutural
robusto converge para o comportamento do `fixed-size`.

## Proveniência

- Stores v2: `simoesthiago/aneel-vectorstores-h12` (8 stores: 2 estratégias ×
  texto/markdown × large/small).
- Run v2: `data/evaluation/runs/retrieval/20260616T033915Z-5e61c8f-dirty`.
- Matriz final: `data/evaluation/report/tables/retrieval_matrix_v2.{md,csv}`.
- Correção: commit do parser/splitter (`src/chunking/article_aware.py`).
