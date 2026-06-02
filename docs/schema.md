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
| `num_paginas` | `int` | Sim | Número de páginas (PDFs) ou `null` (HTML) |
| `metodo_extracao` | `str` | Não | `"pymupdf"`, `"pdfplumber"`, `"ocr"`, `"html_parser"`, `"python_docx"` |
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
pode ser extraído por múltiplas estratégias — cada uma gera uma linha distinta.
Isso viabiliza o benchmark de ingestão (PyMuPDF vs Docling vs LlamaParse) e a
comparação de downstream RAG na Camada 4.

Estratégias atuais: `"pymupdf"` (baseline) e `"docling"`.

**Implicação para a Camada 2:** o `chunk_id` deve incluir a estratégia para que a
FK não seja ambígua: `{id}::{metodo_extracao}::{strategy}::{index}`.

### Notas de design

**Por que uma tabela única em vez de tabelas separadas por tipo?**
O pipeline de RAG trata todos os documentos da mesma forma: texto → chunks →
embeddings → índice. Tabelas separadas complicariam sem benefício — a coluna
`tipo` + `subtipo` permite filtrar quando necessário.

**Por que `metodo_extracao`?**
PDFs antigos (< 2005) são frequentemente escaneados — texto extraído via OCR
tem qualidade diferente. Manuais em DOCX/XLSX exigem extratores diferentes.
A Camada 4 (avaliação) precisa saber isso para interpretar diferenças de
faithfulness entre documentos.

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
| `chunk_id` | `str` | Não | Identificador único do chunk: `{document_id}::{strategy}::{index}` |
| `document_id` | `str` | Não | FK lógica para `documents.id` |
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
| `situacao` | `str` | Sim | Herdado de `documents.situacao` |
| `url_original` | `str` | Não | Herdado de `documents.url_original` |
| `url_consolidado` | `str` | Sim | Herdado de `documents.url_consolidado` |

### Estratégias de chunking

| Estratégia | Uso no benchmark | Observação |
|---|---|---|
| `fixed-size` | Baseline simples | Divide por janela de palavras com overlap |
| `article-aware` | Baseline regulatório | Prioriza `Art.`, `§`, incisos e alíneas |
| `hierarchical` | Parent context | Recupera filhos pequenos e responde com pai mais amplo |

---

## Particionamento do Parquet

```
aneel-corpus/
  data/
    documents/
      tipo=ato_normativo/metodo_extracao=pymupdf/part-0.parquet
      tipo=ato_normativo/metodo_extracao=docling/part-0.parquet
      tipo=procedimento/metodo_extracao=pymupdf/part-0.parquet
      tipo=procedimento/metodo_extracao=docling/part-0.parquet
      tipo=manual/metodo_extracao=pymupdf/part-0.parquet
      tipo=lei/metodo_extracao=html_parser/part-0.parquet
```

Particionado por `(tipo, metodo_extracao)` para que queries como "todos os
procedimentos extraídos com Docling" não precisem ler o dataset inteiro.
Retrocompatível: corpus legado (sem partição `metodo_extracao`) é lido com
inferência `metodo_extracao = "pymupdf"` em `uploader.carregar_corpus_hub()`.

---

## Evolução do schema

Mudanças aqui devem ser registradas em `DECISIONS.md` com motivo.
Nunca remover colunas sem verificar dependências nas Camadas 2-5.
