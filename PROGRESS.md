# PROGRESS.md — Estado Atual do Projeto

Atualizar este arquivo ao início e fim de cada sessão de trabalho.
É a primeira coisa que o Claude lê para saber onde estamos.

---

## Status geral

```
Camada 1 — Ingestão       ▓▓░░░░░░░░  20%  ← AQUI AGORA
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

### Em progresso
- [ ] Reconhecimento do portal ANEEL (`notebooks/exploration/01_aneel_portal_recon.ipynb`)

### Pendente
- [ ] `src/ingestion/scraper.py` — scraping do índice do portal CEDOC
- [ ] `src/ingestion/extractor.py` — extração de texto dos PDFs
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

> **Criar `notebooks/exploration/01_aneel_portal_recon.ipynb` no Google Colab.**
>
> Objetivo: inspecionar o HTML do portal `www2.aneel.gov.br/cedoc/` manualmente antes de escrever qualquer código de scraping. Entender paginação, estrutura da tabela de índice, campos disponíveis, padrão de URL dos PDFs.
>
> Anti-padrão a evitar: começar `scraper.py` sem este reconhecimento.

---

## Bloqueios e riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Portal ANEEL muda estrutura HTML | Média | Scraper com seletores nomeados, fácil de atualizar |
| PDFs antigos (< 2005) são scanned (imagem) | Alta | `extractor.py` com OCR fallback via Tesseract |
| Rate limiting do portal | Média | `time.sleep()` entre requisições + checkpoint |
