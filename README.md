# ANEEL RAG Benchmark

Benchmark comparativo de estratégias de RAG (Retrieval-Augmented Generation) aplicadas às Resoluções Normativas da ANEEL. O projeto scrapa o portal público da agência, compara múltiplas estratégias com métricas objetivas e disponibiliza um chatbot funcional para consulta regulatória.

---

## Arquitetura

O pipeline é organizado em 5 camadas independentes:

1. **Ingestão** — scraping do portal ANEEL, extração de texto dos PDFs, parsing de estrutura (seções, artigos), upload para HuggingFace Hub
2. **Processamento** — estratégias de chunking (fixed-size, semântico, hierárquico), geração de embeddings, indexação em FAISS
3. **RAG** — implementações comparáveis: Naive RAG, Semantic RAG, Hierarchical RAG, GraphRAG — todas com interface comum `query(pergunta) → resposta`
4. **Avaliação** — benchmark com 20-30 perguntas regulatórias reais; métricas: recall@k, faithfulness, latência
5. **Interface** — chatbot Streamlit hospedado no HuggingFace Spaces, usando a estratégia vencedora do benchmark

---

## Infraestrutura

Todo o processamento e armazenamento de dados é feito fora da máquina local, com custo zero:

| Componente | Onde roda |
|---|---|
| Desenvolvimento e scraping | Google Colab |
| Scraping recorrente | GitHub Actions |
| PDFs, Parquet e índices FAISS | HuggingFace Hub (dataset repo) |
| Código-fonte | GitHub |
| Chatbot | HuggingFace Spaces (Streamlit) |

O repositório Git contém **apenas código, configuração e documentação** — nenhum dado.

---

## Como rodar

> Em construção. As instruções serão adicionadas ao longo do desenvolvimento de cada camada.

---

## Dataset

> Link para o dataset no HuggingFace Hub: a ser publicado após a Camada 1 (Ingestão).

---

## Resultados

> Tabela comparativa das estratégias RAG a ser publicada após a Camada 4 (Avaliação).

| Estratégia | Recall@5 | Faithfulness | Latência média |
|---|---|---|---|
| Naive RAG | — | — | — |
| Semantic RAG | — | — | — |
| Hierarchical RAG | — | — | — |
| GraphRAG | — | — | — |
