# Contexto do Projeto para Claude Code

## Quem é o desenvolvedor

Estudante de Engenharia de Produção (UFRJ, formando 2026), estagiário na Kearney Brasil com foco em utilities (setor elétrico e saneamento). Objetivo técnico: tornar-se Forward Deployed Engineer (FDE). Nível em Python: básico. Sem experiência prévia com APIs de IA, deployment ou ML aplicado.

**Como ajudar:**
- Explique o "por quê" antes do "como"
- Escreva código limpo, comentado e auditável — como um engenheiro sênior escreveria para um júnior ler
- Conecte os conceitos ao contexto de FDE e deployment real
- Idioma: português brasileiro, termos técnicos em inglês quando forem padrão de mercado

---

## O Projeto

Benchmark comparativo de estratégias RAG sobre Resoluções Normativas da ANEEL, com chatbot funcional no HuggingFace Spaces.

**Escopo atual: Camada 1 — Ingestão.**

---

## Premissa Fundamental

O repositório Git contém **apenas código, configuração e documentação**.

- PDFs, Parquets e índices FAISS **nunca tocam a máquina local**
- O pipeline roda no Google Colab (desenvolvimento) e GitHub Actions (produção)
- Dados são gerados em memória e publicados direto no HuggingFace Hub

---

## Arquitetura (5 camadas)

```
CAMADA 1 — INGESTÃO        src/ingestion/
CAMADA 2 — PROCESSAMENTO   src/chunking/ + src/embeddings/ + src/vectorstore/
CAMADA 3 — RAG             src/rag/
CAMADA 4 — AVALIAÇÃO       src/evaluation/
CAMADA 5 — INTERFACE       src/app/
```

---

## Fonte de Dados

**Portal:** `www2.aneel.gov.br/cedoc/`

**Padrão de URL:**
```
https://www2.aneel.gov.br/cedoc/ren{ano}{numero}.pdf
# Exemplo: REN 1000/2021
https://www2.aneel.gov.br/cedoc/ren20211000.pdf

# Versão consolidada (com alterações incorporadas)
https://www2.aneel.gov.br/cedoc/bren2010414.pdf
```

**Foco:** Resoluções Normativas (`ren`) — todas disponíveis (1996–hoje).

**Estratégia:** scraping via índice do portal (não enumeração de URL), para capturar metadados estruturados junto com os PDFs.

---

## Decisões de Arquitetura

| Decisão | Escolha | Motivo |
|---|---|---|
| Execução do pipeline | Google Colab → GitHub Actions | Zero infra local |
| Armazenamento de dados | HuggingFace Hub | Grátis, público, suporta LFS |
| Vector DB | FAISS (arquivo) | Sem servidor; index como artefato reproduzível |
| Formato de dados | Parquet | Padrão de mercado para dados tabulares em ML |
| Chatbot | HuggingFace Spaces (Streamlit) | Grátis, integrado com Hub |

---

## Infraestrutura (custo zero)

```
Desenvolvimento     → Google Colab
Scraping recorrente → GitHub Actions
PDFs brutos         → HF Hub dataset repo (LFS)
Dados estruturados  → HF Hub dataset repo (Parquet)
Índices FAISS       → HF Hub dataset repo (.faiss)
Chatbot             → HuggingFace Spaces (Streamlit)
```
