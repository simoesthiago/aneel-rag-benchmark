# PROGRESS.md — Estado Atual do Projeto

Atualizar este arquivo ao início e fim de cada sessão de trabalho.
É a primeira coisa que o Claude lê para saber onde estamos.

---

## Status geral

```
Camada 1 — Ingestão       ▓▓▓░░░░░░░  25%  ← AQUI AGORA
Camada 2 — Processamento  ░░░░░░░░░░   0%
Camada 3 — RAG            ░░░░░░░░░░   0%
Camada 4 — Avaliação      ░░░░░░░░░░   0%
Camada 5 — Interface      ░░░░░░░░░░   0%
```

---

## Camada 1 — Ingestão (`src/ingestion/`)

### Concluído
- [x] Estrutura de pastas do projeto (todas as 5 camadas)
- [x] `.gitignore` — bloqueia dados (`*.pdf`, `*.parquet`, `*.faiss`) e CLAUDE.md
- [x] `requirements.txt` (prod: Colab/Actions) e `requirements-dev.txt` (local)
- [x] `pyproject.toml` — metadados do projeto
- [x] `Makefile` — atalhos `install`, `install-prod`, `test`, `lint`, `format`
- [x] `.env.example` — template de variáveis de ambiente
- [x] `src/config/settings.py` — configurações centralizadas com lazy loading
- [x] `DECISIONS.md`, `PROGRESS.md`, `docs/schema.md` — controle de evolução
- [x] Repositório publicado no GitHub (`simoesthiago/aneel-rag-benchmark`)
- [x] Reconhecimento do portal ANEEL (via Playwright)
- [x] Definição do escopo do corpus (4 fontes, ver DECISIONS.md)

### Achados do reconhecimento (2026-05-28)
- `www2.aneel.gov.br/cedoc/` retorna **HTTP 403.14** — sem índice HTML
- **Power BI** "Gestão do Estoque Regulatório" é o índice real de atos normativos (~1.460 atos, API REST)
- **PRODIST/PRORET** estão em `git.aneel.gov.br/publico/centralconteudo/` (GitLab público com API)
- **Procedimentos Regulatórios** tem 5 subcategorias: PRODIST, PRORET, Proc. de Rede, EE/P&D, Transmissão
- **Manuais** tem 19 subcategorias com formatos variados (PDF, Excel, Word)
- **Leis estruturantes** estão em `planalto.gov.br` (HTML estático, 4 leis)
- `leis.org` é agregador terceiro — NÃO é fonte de dados (útil só como referência de categorias)

### Em progresso
- [ ] Reconhecimento detalhado do notebook (`notebooks/exploration/01_aneel_portal_recon.ipynb`) — rodar no Colab

### Pendente
- [ ] `src/ingestion/scraper.py` — scraping dos atos normativos via Power BI API + cedoc/
- [ ] `src/ingestion/scraper_procedimentos.py` — coleta de procedimentos via GitLab API
- [ ] `src/ingestion/scraper_manuais.py` — coleta de manuais via gov.br
- [ ] `src/ingestion/scraper_leis.py` — coleta de leis via planalto.gov.br (HTML)
- [ ] `src/ingestion/extractor.py` — extração de texto (PDF, HTML, DOCX, XLSX)
- [ ] `src/ingestion/parser.py` — parsing de estrutura (seções, artigos)
- [ ] `src/ingestion/uploader.py` — publicação no HuggingFace Hub
- [ ] `tests/test_ingestion.py` — testes unitários de ingestão
- [ ] Dataset publicado em `simoesthiago/aneel-corpus` no HF Hub

---

## Camada 2 — Processamento (`src/chunking/` + `src/embeddings/` + `src/vectorstore/`)

- [ ] Aguarda Camada 1 concluída

---

## Camada 3 — RAG (`src/rag/`)

- [ ] Aguarda Camada 2 concluída

---

## Camada 4 — Avaliação (`src/evaluation/`)

- [ ] Aguarda Camada 3 concluída

---

## Camada 5 — Interface (`src/app/`)

- [ ] Aguarda Camada 4 concluída

---

## Próximo passo concreto

> **Rodar o notebook `01_aneel_portal_recon.ipynb` no Google Colab.**
>
> Objetivo: validar as descobertas do Playwright (Power BI API, padrões de URL do cedoc/, GitLab API)
> com código Python real. Testar extração de texto de um PDF de exemplo.
>
> Depois: implementar `src/ingestion/scraper.py` começando pela fonte mais estruturada (Power BI API → cedoc/).

---

## Bloqueios e riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Power BI API muda estrutura do payload | Média | Documentar formato atual, validação no scraper |
| Portal ANEEL aplica rate limiting | Média | `time.sleep()` entre requisições + checkpoint |
| PDFs antigos (< 2005) são scanned (imagem) | Alta | `extractor.py` com OCR fallback via Tesseract |
| Manuais em DOCX/XLSX exigem extratores extras | Alta | `python-docx`, `openpyxl` no requirements.txt |
| GitLab ANEEL muda estrutura de pastas | Baixa | API REST com listagem dinâmica, não paths hardcoded |
| Volume total muito grande para Colab gratuito | Média | Processamento em batches com checkpointing |
