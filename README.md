# ANEEL RAG Benchmark

Benchmark comparativo de estratégias de RAG aplicadas ao ecossistema regulatório
da ANEEL. O projeto coleta documentos públicos, estrutura chunks citáveis,
compara estratégias de recuperação e mede qualidade regulatória, custo e
latência.

O foco deixou de ser apenas "qual RAG vence" e passou a ser:

> Qual combinação de chunking, retrieval, geração e citação normativa produz a
> melhor resposta regulatória com norma vigente, fonte correta, custo aceitável e
> latência viável?

---

## Escopo do corpus

O corpus cobre quatro famílias de documentos:

| Fonte | Exemplos | Status |
|---|---|---|
| Atos normativos | RENs, REHs, despachos e outros atos do estoque regulatório | Wave 1/2 |
| Procedimentos regulatórios | PRODIST, PRORET, Procedimentos de Rede, EE/P&D, Transmissão | Wave 1/2/3 |
| Manuais, modelos e instruções | Guias operacionais, modelos e planilhas públicas | Wave 3 |
| Leis estruturantes | Lei 9.427/1996, Lei 8.987/1995, Lei 9.074/1995, Lei 13.848/2019 | Wave 1 |

---

## Arquitetura

O pipeline é organizado em 5 camadas:

1. **Ingestão** - coleta documentos públicos, extrai texto, valida schema e publica Parquet no HuggingFace Hub.
2. **Processamento** - gera chunks `fixed-size`, `article-aware` e `hierarchical`, embeddings e índices.
3. **RAG** - compara BM25, dense FAISS, hybrid BM25+dense e hierarchical parent-child.
4. **Avaliação** - mede retrieval, citação, status normativo, latência e métricas LLM opcionais.
5. **Interface** - chatbot Streamlit no HuggingFace Spaces usando a melhor estratégia validada.

GraphRAG fica documentado como fase avançada posterior. Ele não é caminho crítico
do MVP porque BM25/hybrid tende a entregar ganho mais barato e explicável para
documentos regulatórios cheios de siglas, números e referências normativas.

---

## Implementação em ondas

| Onda | Conteúdo | Objetivo |
|---|---|---|
| Wave 1 | 4 leis + amostra de RENs + PRODIST Módulo 1 | Provar pipeline completo |
| Wave 2 | RENs vigentes + todos os módulos PRODIST | Expandir benchmark operacional |
| Wave 3 | Manuais, PRORET, demais atos, OCR e formatos DOCX/XLSX | Completar corpus |

---

## Estratégias comparadas

| Estratégia | Chunking | Retrieval | Observação |
|---|---|---|---|
| BM25 baseline | `article-aware` ou `fixed-size` | Lexical | Forte para siglas, números e artigos |
| Dense FAISS | `fixed-size` ou `article-aware` | Embeddings BGE-M3 | Baseline semântico zero-custo |
| Hybrid | Mesmo corpus | BM25 + dense via RRF | Primeiro candidato para domínio regulatório |
| Hierarchical | Parent-child | Busca filhos, responde com contexto pai | Melhor para artigos/seções |

---

## Métricas do benchmark

| Grupo | Métricas |
|---|---|
| Retrieval | `recall@5`, `precision@5`, `mrr@5`, `article_hit@5` |
| Resposta | `citation_accuracy`, `status_accuracy`, `faithfulness`, `answer_correctness` |
| Operacional | `latency_avg`, `latency_p95`, custo por consulta e tempo de build |

`faithfulness` e `answer_correctness` são opcionais: rodam apenas quando
`LLM_API_KEY` estiver configurada. Sem chave, o benchmark registra
`skipped_no_llm_key` e continua.

---

## Infraestrutura

Todo processamento pesado roda fora da máquina local:

| Componente | Onde roda |
|---|---|
| Desenvolvimento e scraping | Google Colab |
| Scraping recorrente | GitHub Actions |
| PDFs, Parquet e índices FAISS | HuggingFace Hub |
| Código-fonte | GitHub |
| Chatbot | HuggingFace Spaces |

O repositório Git contém apenas código, configuração e documentação. Dados,
PDFs, Parquet e índices ficam fora do Git.

---

## Como rodar

```bash
make install
make test
```

Para ambiente de produção/Colab:

```bash
make install-prod
```

O dataset público será publicado em `simoesthiago/aneel-corpus` após a Wave 1.
