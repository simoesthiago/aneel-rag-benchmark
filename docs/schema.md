# Schema do Corpus — ANEEL RAG Benchmark

Este arquivo define a estrutura de dados que a Camada 1 (Ingestão) produz
e que todas as camadas seguintes consomem. **Alterar o schema depois que
as Camadas 2-5 estiverem implementadas tem custo alto — decidir antes.**

---

## Dataset no HuggingFace Hub

**Repositório:** `simoesthiago/aneel-corpus`
**Formato:** Parquet (particionado por tipo de documento)
**Cobertura:** Ecossistema regulatório completo da ANEEL

---

## Escopo do corpus (4 fontes)

| Fonte | Tipo | Exemplos | Volume estimado |
|---|---|---|---|
| Gestão do Estoque Regulatório | Atos normativos | RENs, REHs, Despachos | ~1.460 atos (193 RENs vigentes) |
| Procedimentos Regulatórios (GitLab ANEEL) | Procedimentos técnicos | PRODIST (11 mód.), PRORET, Regras de Transmissão (6 mód.) | ~30 documentos |
| Procedimentos de Rede (SharePoint ONS) | Procedimentos operacionais | 9 módulos, ~50 submódulos, tipos RS/OP/PR/CR/RQ/IN | ~165 documentos |
| Manuais, Modelos e Instruções | Guias operacionais | Manuais de distribuição, tarifas, geração | ~100+ documentos |
| Leis estruturantes | Legislação federal | Lei 9.427, Lei 8.987, Lei 9.074, Lei 13.848 | 4 documentos |

---

## Tabela principal: `documents`

Cada linha é **um documento** do corpus, independente da fonte.

| Coluna | Tipo Python | Nullable | Descrição |
|---|---|---|---|
| `id` | `str` | Não | Identificador único (ver padrão abaixo) |
| `tipo` | `str` | Não | Categoria: `"ato_normativo"`, `"procedimento"`, `"manual"`, `"lei"` |
| `subtipo` | `str` | Sim | Ex.: `"ren"`, `"reh"`, `"prodist"`, `"proret"`, `"lei_federal"` |
| `numero` | `str` | Sim | Número do documento (ex.: `"1000"`, `"Módulo 8"`) |
| `ano` | `int` | Sim | Ano de publicação ou última atualização |
| `titulo` | `str` | Não | Nome/ementa do documento |
| `assunto` | `str` | Sim | Assunto ou área (quando disponível no metadado) |
| `situacao` | `str` | Sim | `"vigente"`, `"revogada"`, `"consolidada"` (atos) ou `null` (manuais/leis) |
| `data_publicacao` | `str` | Sim | Data no formato `"YYYY-MM-DD"` (quando disponível) |
| `fonte` | `str` | Não | Origem: `"cedoc"`, `"gitlab"`, `"gov_br"`, `"planalto"`, `"ons_org_br"` |
| `url_original` | `str` | Não | URL do documento na fonte original |
| `url_consolidado` | `str` | Sim | URL da versão consolidada (atos: `bren...`), se existir |
| `formato_original` | `str` | Não | `"pdf"`, `"html"`, `"docx"`, `"xlsx"` |
| `texto_bruto` | `str` | Não | Texto completo extraído do documento |
| `num_paginas` | `int` | Sim | Número de páginas (PDFs) ou `null` (HTML/DOCX/XLSX) |
| `metodo_extracao` | `str` | Não | Formato de saída: `"texto"` ou `"markdown"` (eixo do benchmark; vira partição no Hub) |
| `extrator` | `str` | Não | Ferramenta concreta: `"pymupdf"`, `"pymupdf4llm"`, `"html_parser"`, `"html2markdown"`, `"python_docx"`, `"mammoth"`, `"openpyxl"`, `"pandas_tabulate"` |
| `qualidade_extracao` | `float` | Sim | Score 0-1 estimado (% de páginas sem anomalia) |
| `hf_path` | `str` | Sim | Caminho do arquivo bruto no HF Hub (LFS) |
| `scraped_at` | `str` | Não | Timestamp da extração: `"YYYY-MM-DDTHH:MM:SSZ"` |

### Padrão de `id`

O `id` é composto pelo tipo + identificador legível:

```
Atos normativos:    "ren-2021-1000", "reh-2026-3589"
Procedimentos:      "prodist-modulo-08", "proret-submódulo-2.1", "proc-rede-1-1-op"
Manuais:            "manual-distribuicao-cartilha-gd"
Leis:               "lei-9427-1996", "lei-8987-1995"
```

**Por que string?** Facilita joins, lookup e debugging. `"ren-2021-1000"` é
autoexplicativo em logs — um número puro `1000` não é.

### Unicidade e benchmark de extração (Opção A)

A chave de uma linha é `(id, metodo_extracao)`, não só `id`. O mesmo documento
aparece como `texto` E como `markdown` — duas linhas distintas, mesmo `id`,
`metodo_extracao` diferente. Isso viabiliza o benchmark de ingestão e a
comparação de downstream RAG na Camada 4.

Valores de `metodo_extracao`: **só** `"texto"` e `"markdown"`. A ferramenta real
fica na coluna `extrator` (rastreio, não chave). Mapa formato_arquivo × formato_saida:

|        | `metodo_extracao=texto` | `metodo_extracao=markdown` |
|--------|-------------------------|----------------------------|
| `pdf`  | `extrator=pymupdf`      | `extrator=pymupdf4llm`     |
| `html` | `extrator=html_parser`  | `extrator=html2markdown`   |
| `docx` | `extrator=python_docx`  | `extrator=mammoth`         |
| `xlsx` | `extrator=openpyxl`     | `extrator=pandas_tabulate` |

**Implicação para a Camada 2:** o `chunk_id` deve incluir `metodo_extracao` para
que a FK não seja ambígua: `{id}::{metodo_extracao}::{strategy}::{index}`.

### Notas de design

**Por que uma tabela única em vez de tabelas separadas por tipo?**
O pipeline de RAG trata todos os documentos da mesma forma: texto → chunks →
embeddings → índice. Tabelas separadas complicariam sem benefício — a coluna
`tipo` + `subtipo` permite filtrar quando necessário.

**Por que separar `metodo_extracao` e `extrator`?**
`metodo_extracao` ∈ {texto, markdown} é o **eixo do benchmark** — só dois valores,
exatos, simétricos por formato de arquivo. Particionar por isso dá ao Hub uma
estrutura limpa (2 pastas por tipo) e queries triviais ("dame só o markdown").
A ferramenta concreta (`pymupdf`, `mammoth`, …) viaja em `extrator` como metadado
de rastreio: útil em manuais (formatos mistos, vários extratores na mesma
partição) e na Camada 4 para interpretar diferenças de faithfulness.

**Por que `qualidade_extracao`?**
Permite filtrar documentos problemáticos antes do benchmark. Um PDF com 30%
de páginas ilegíveis não deve entrar no conjunto de avaliação.

**Por que `formato_original`?**
Documentos vêm em formatos diferentes (PDF, HTML, DOCX, XLSX). O extrator
precisa saber qual parser usar, e a Camada 4 pode querer analisar qualidade
por formato.

**Por que `url_consolidado` separado?**
Versões consolidadas (`bren...`) incorporam alterações posteriores — são mais
úteis para RAG (texto completo e atualizado). Mas a versão original é
necessária para rastreabilidade histórica.

---

## Tabela derivada: `chunks`

Cada linha representa um trecho recuperável do corpus. Esta tabela é derivada
de `documents`; a tabela principal não muda e continua sendo a fonte de verdade
da Camada 1.

| Coluna | Tipo Python | Nullable | Descrição |
|---|---|---|---|
| `chunk_id` | `str` | Não | Identificador único do chunk: `{document_id}::{metodo_extracao}::{strategy}::{index}` |
| `document_id` | `str` | Não | Parte da FK lógica para `documents.id` |
| `metodo_extracao` | `str` | Não | Parte da FK lógica para `documents.metodo_extracao`; distingue chunks de `texto` e `markdown` |
| `extrator` | `str` | Sim | Herdado de `documents.extrator`; ferramenta concreta que produziu o texto base |
| `parent_chunk_id` | `str` | Sim | Chunk pai em estratégias hierárquicas |
| `chunk_strategy` | `str` | Não | `"fixed-size"`, `"article-aware"`, `"hierarchical"` ou `"hierarchical-child"` |
| `chunk_level` | `str` | Não | `"chunk"`, `"article"`, `"section"` ou `"paragraph"` |
| `chunk_index` | `int` | Não | Ordem do chunk dentro do documento/estratégia |
| `texto` | `str` | Não | Texto do chunk usado em retrieval e geração |
| `secao` | `str` | Sim | Título/capítulo/seção mais próximo |
| `artigo` | `str` | Sim | Ex.: `"Art. 353"` |
| `paragrafo` | `str` | Sim | Ex.: `"§ 1º"` |
| `inciso` | `str` | Sim | Ex.: `"III"` |
| `alinea` | `str` | Sim | Ex.: `"a"` |
| `citation_label` | `str` | Não | Rótulo curto para citação na resposta |
| `tipo` | `str` | Não | Herdado de `documents.tipo` |
| `subtipo` | `str` | Sim | Herdado de `documents.subtipo` |
| `numero` | `str` | Sim | Herdado de `documents.numero` |
| `ano` | `int` | Sim | Herdado de `documents.ano` |
| `titulo` | `str` | Não | Herdado de `documents.titulo` |
| `assunto` | `str` | Sim | Herdado de `documents.assunto` |
| `situacao` | `str` | Sim | Herdado de `documents.situacao` |
| `fonte` | `str` | Não | Herdado de `documents.fonte` |
| `formato_original` | `str` | Não | Herdado de `documents.formato_original` |
| `qualidade_extracao` | `float` | Sim | Herdado de `documents.qualidade_extracao` |
| `url_original` | `str` | Não | Herdado de `documents.url_original` |
| `url_consolidado` | `str` | Sim | Herdado de `documents.url_consolidado` |

### Estratégias de chunking

| Estratégia | Uso no benchmark | Observação |
|---|---|---|
| `fixed-size` | Baseline simples | Divide por janela de palavras com overlap |
| `article-aware` | Baseline regulatório | Prioriza `Art.`, `Artigo`, `§`, incisos e alíneas; fallback por seções/parágrafos |
| `hierarchical` | Parent context | Gera pais estruturais e filhos `hierarchical-child` menores para retrieval |

---

## Artefato derivado: `embeddings`

Embeddings são gerados sobre `chunks.texto`, nunca sobre o documento inteiro.
O `chunk_id` é a chave lógica entre vetor e metadados. A Camada 2.2 produz
vetores em memória para a Camada 2.3; o artefato persistente será o índice FAISS
com metadados separados.

| Campo | Tipo | Descrição |
|---|---|---|
| `vectors` | `float32[n_chunks, dimension]` | Matriz de embeddings na mesma ordem de `metadata` |
| `metadata` | `DataFrame` | Chunks e metadados, incluindo `chunk_id`, `texto`, `citation_label`, URLs e estrutura legal |
| `manifest` | `dict` | Provider, modelo, dimensão, filtros de chunk, contagem e timestamp |

### Providers de embedding

| Provider | Modelo | Uso |
|---|---|---|
| `openai` | `text-embedding-3-large` | Caminho principal de qualidade |
| `openai` | `text-embedding-3-small` | Baseline barato |
| `hash` | `hash` | Testes offline, sem API |

---

## Particionamento do Parquet

```
aneel-corpus/
  data/
    documents/
      tipo=ato_normativo/metodo_extracao=texto/part-0.parquet
      tipo=ato_normativo/metodo_extracao=markdown/part-0.parquet
      tipo=procedimento/metodo_extracao=texto/part-0.parquet
      tipo=procedimento/metodo_extracao=markdown/part-0.parquet
      tipo=manual/metodo_extracao=texto/part-0.parquet
      tipo=manual/metodo_extracao=markdown/part-0.parquet
      tipo=lei/metodo_extracao=texto/part-0.parquet
      tipo=lei/metodo_extracao=markdown/part-0.parquet
    chunks/
      chunk_strategy=fixed-size/metodo_extracao=texto/tipo=ato_normativo/part-0.parquet
      chunk_strategy=fixed-size/metodo_extracao=markdown/tipo=ato_normativo/part-0.parquet
      chunk_strategy=article-aware/metodo_extracao=texto/tipo=procedimento/part-0.parquet
      chunk_strategy=hierarchical/metodo_extracao=markdown/tipo=lei/part-0.parquet
      chunk_strategy=hierarchical-child/metodo_extracao=markdown/tipo=lei/part-0.parquet
```

Documentos são particionados por `(tipo, metodo_extracao)` — **exatamente 2
partições por tipo**. A coluna `extrator` (ferramenta concreta) viaja dentro do
Parquet, não particiona. Em manuais (formatos heterogêneos), a partição
`markdown` pode conter linhas com `extrator ∈ {pymupdf4llm, mammoth,
pandas_tabulate, html2markdown}`.

Chunks são particionados por `(chunk_strategy, metodo_extracao, tipo)` e gravados
em `data/chunks/`. Ao publicar chunks, o pipeline substitui apenas `data/chunks/`
e preserva `data/documents/`, porque chunks são artefatos derivados da Camada 2.

Embeddings crus não são publicados como Parquet nesta fase. Na Camada 2.3, FAISS
será publicado com `index.faiss`, `metadata.parquet` e `manifest.json`, usando o
mesmo provider/modelo tanto para indexação quanto para consulta.

Não há mais retrocompatibilidade com corpus legado: o uploader exige que todo
Parquet tenha partição `metodo_extracao=`. A migração foi feita uma única vez com
`python -m src.ingestion.run --todas --estrategia texto --limpar-estrutura`.

---

## Evolução do schema

Mudanças aqui devem ser registradas em `DECISIONS.md` com motivo.
Nunca remover colunas sem verificar dependências nas Camadas 2-5.
