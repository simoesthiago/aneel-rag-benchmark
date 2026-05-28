# Schema do Corpus — ANEEL RAG Benchmark

Este arquivo define a estrutura de dados que a Camada 1 (Ingestão) produz
e que todas as camadas seguintes consomem. **Alterar o schema depois que
as Camadas 2-5 estiverem implementadas tem custo alto — decidir antes.**

---

## Dataset no HuggingFace Hub

**Repositório:** `simoesthiago/aneel-corpus`
**Formato:** Parquet (particionado por ano)
**Cobertura planejada:** Resoluções Normativas (REN) de 1996 até hoje

---

## Tabela principal: `resolutions`

Cada linha é **uma Resolução Normativa**.

| Coluna | Tipo Python | Nullable | Descrição |
|---|---|---|---|
| `numero` | `int` | Não | Número da resolução (ex.: 1000) |
| `ano` | `int` | Não | Ano de publicação (ex.: 2021) |
| `id` | `str` | Não | Identificador único: `"REN-{ano}-{numero:04d}"` |
| `ementa` | `str` | Não | Descrição oficial do ato (do índice do portal) |
| `assunto` | `str` | Sim | Assunto classificado pelo portal |
| `situacao` | `str` | Não | `"vigente"` ou `"revogada"` |
| `data_publicacao` | `str` | Sim | Data no formato `"YYYY-MM-DD"` (quando disponível) |
| `pdf_url` | `str` | Não | URL original no portal ANEEL |
| `pdf_consolidado_url` | `str` | Sim | URL da versão consolidada (`bren...`), se existir |
| `texto_bruto` | `str` | Não | Texto completo extraído do PDF |
| `num_paginas` | `int` | Sim | Número de páginas do PDF |
| `metodo_extracao` | `str` | Não | `"pymupdf"`, `"pdfplumber"` ou `"ocr"` |
| `qualidade_extracao` | `float` | Sim | Score 0-1 estimado (% de páginas sem anomalia) |
| `hf_pdf_path` | `str` | Sim | Caminho do PDF bruto no HF Hub (LFS) |
| `scraped_at` | `str` | Não | Timestamp da extração: `"YYYY-MM-DDTHH:MM:SSZ"` |

### Notas de design

**Por que `id` como string?**
Facilita joins e lookup sem risco de colisão entre anos. `"REN-2021-1000"` é
autoexplicativo em logs e erros — número puro `1000` não é.

**Por que `metodo_extracao`?**
PDFs antigos (< 2005) são frequentemente escaneados — texto extraído via OCR
tem qualidade diferente. A Camada 4 (avaliação) precisa saber isso para
interpretar diferenças de faithfulness entre documentos.

**Por que `qualidade_extracao`?**
Permite filtrar documentos problemáticos antes do benchmark. Um PDF com 30%
de páginas ilegíveis não deve entrar no conjunto de avaliação.

**Por que `pdf_consolidado_url` separado?**
Versões consolidadas (`bren...`) incorporam alterações posteriores — são mais
úteis para RAG (texto completo e atualizado). Mas a versão original é
necessária para rastreabilidade histórica.

---

## Particionamento do Parquet

```
aneel-corpus/
  data/
    resolutions/
      ano=1996/part-0.parquet
      ano=1997/part-0.parquet
      ...
      ano=2026/part-0.parquet
```

Particionado por `ano` para que queries como "RENs de 2020-2023" não precisem
ler o dataset inteiro — pandas e `datasets` da HF suportam predicate pushdown.

---

## Evolução do schema

Mudanças aqui devem ser registradas em `DECISIONS.md` com motivo.
Nunca remover colunas sem verificar dependências nas Camadas 2-5.
