# ANEEL RAG Benchmark

Benchmark comparativo de estratégias de RAG aplicadas ao ecossistema regulatório da ANEEL. O projeto coleta documentos públicos, estrutura chunks citáveis, compara estratégias de recuperação e mede qualidade regulatória, custo e latência.

> Qual combinação de chunking, retrieval, geração e citação normativa produz a melhor resposta regulatória com norma vigente, fonte correta, custo aceitável e latência viável?

---

## Escopo do corpus

O corpus cobre cinco famílias de documentos:

| Fonte | Exemplos | Status |
|---|---|---|
| Atos normativos | RENs, REHs, despachos e outros atos do estoque regulatório | ~990 docs |
| Procedimentos regulatórios | PRODIST (11 mód.), Regras de Transmissão (6 mód.), PRORET | ~395 docs |
| Procedimentos de Rede (ONS) | 9 módulos, ~165 submódulos vigentes (tipos OP/RS/PR/CR/IN/RQ) | ~165 docs |
| Manuais, modelos e instruções | Guias operacionais, modelos e planilhas públicas | ~85 docs |
| Leis estruturantes | Lei 9.427/1996, Lei 8.987/1995, Lei 9.074/1995, Lei 13.848/2019 | 4 docs |

---

## Arquitetura

O pipeline de construção é organizado em 5 camadas:

| # | Camada | Responsabilidade | Status |
|---|---|---|---|
| 1 | **Ingestão** | Coleta documentos públicos, extrai texto, valida schema e publica Parquet no HuggingFace Hub | ✅ |
| 2 | **Processamento** | Gera chunks (`fixed-size`, `article-aware`, `hierarchical-child`), embeddings e índices FAISS | ✅ |
| 3 | **RAG** | Compara Dense FAISS, Hierarchical parent-child e reranking opcional | 🔄 |
| 4 | **Avaliação** | Mede retrieval, citação, status normativo, latência e métricas LLM opcionais | 🔄 |
| 5 | **Interface** | Chatbot Streamlit no HuggingFace Spaces usando a melhor estratégia validada | ⬜ |

Legenda: ✅ concluída · 🔄 em construção · ⬜ não iniciada.

---

## Benchmark de extração

Cada documento é extraído em **duas versões** — o eixo central do benchmark de ingestão:

| Estratégia | Ferramenta por formato | Coluna `metodo_extracao` |
|---|---|---|
| Texto plano | PyMuPDF (PDF), BeautifulSoup (HTML), python-docx (DOCX), openpyxl (XLSX) | `"texto"` |
| Markdown estruturado | PyMuPDF4LLM (PDF), html2text (HTML), mammoth (DOCX), pandas+tabulate (XLSX) | `"markdown"` |

A ferramenta concreta fica na coluna `extrator` para rastreio. O Hub é particionado por `tipo=X/metodo_extracao={texto,markdown}/` — exatamente 2 partições por tipo.

---

## Estratégias de chunking

| Estratégia | Unidade | Observação |
|---|---|---|
| `fixed-size` | Janela fixa de tokens com overlap | Baseline agnóstico de estrutura — referência mínima para comparar as demais |
| `article-aware` | Artigos, seções e parágrafos do documento regulatório | Respeita a granularidade citável da norma — favorece `article_hit@5` e `citation_accuracy` |
| `hierarchical-child` | Filhos pequenos com referência ao chunk pai | Busca no filho, responde com contexto do pai — testa a hipótese de melhor recall em normas longas |

---

## Estratégias de retrieval

| Estratégia | Chunking | Retrieval | Observação |
|---|---|---|---|
| Dense FAISS | `fixed-size` ou `article-aware` | Embeddings OpenAI (`text-embedding-3-large` / `-3-small`) | Baseline semântico |
| Hierarchical flat | `hierarchical-child` | Busca filhos e devolve filhos | Controle para isolar o efeito parent-child |
| Hierarchical parent-child | `hierarchical-child` | Busca filhos, devolve pais deduplicados | Testa contexto pai para normas longas |
| Rerank opcional | Qualquer estratégia acima | Cohere Rerank sobre candidatos FAISS | Segunda fase; não substitui o baseline sem rerank |

---

## Matriz de vector stores publicadas

A Camada 2 publica uma vector store FAISS por combinação do produto cartesiano abaixo, totalizando **12 índices** no Hub. Cada índice é um pacote autocontido (`index.faiss` + `metadata.parquet` + `manifest.json`, com `parents.parquet` adicional para `hierarchical-child`).

| Eixo | Valores | Cardinalidade |
|---|---|---|
| Modelo de embedding | `text-embedding-3-large`, `text-embedding-3-small` | 2 |
| Estratégia de chunking | `fixed-size`, `article-aware`, `hierarchical-child` | 3 |
| Método de extração | `markdown`, `texto` | 2 |
| **Total** | 2 × 3 × 2 | **12** |

Layout no Hub (Hive-style, consistente com `data/chunks/`):

```
data/vectorstores/
  provider=openai/
    model=<embedding-model>/
      chunk_strategy=<strategy>/
        metodo_extracao=<metodo>/
          index.faiss
          metadata.parquet
          manifest.json
          parents.parquet   # apenas para hierarchical-child
```

Geração via `make vectorstore-all` (a matriz) ou `make vectorstore-main` (apenas `large + article-aware + markdown`, a entrega mínima da Camada 2).

---

## Métricas do benchmark

| Grupo | Métricas |
|---|---|
| Retrieval | `recall_at_k`, `doc_recall_at_k`, `precision_at_k`, `mrr_at_k`, `ndcg_at_k` |
| Resposta | `citation_accuracy`, `status_accuracy`, `faithfulness`, `answer_correctness` |
| Operacional | `latency_avg`, `latency_p95`, custo por consulta e tempo de build |

No benchmark de retrieval, perguntas `source_only` ficam rastreadas no detalhe,
mas não entram nas métricas agregadas porque não têm suporte textual confiável
no corpus extraído.

`recall_at_k` mede cobertura de trecho/fonte esperada. `doc_recall_at_k` mede
se o documento esperado apareceu no top-k, mesmo quando o trecho exato não foi
recuperado. Essa separação evita confundir falha de retrieval com falha de
granularidade de chunk.

`faithfulness` e `answer_correctness` são opcionais: rodam apenas quando `LLM_API_KEY` estiver configurada. Sem chave, o benchmark registra `skipped_no_llm_key` e continua.

O smoke RAG ponta-a-ponta roda com `make benchmark-rag`. Ele avalia duas
configurações controladas — baseline atual e baseline com rerank — e grava os
resultados em `data/evaluation/results/rag-50/`. Com chave configurada, há
custo de geração e de juiz LLM; sem `OPENAI_API_KEY` ou `LLM_API_KEY`, o
gerador cai em fallback extrativo. A segunda configuração usa rerank e exige
`COHERE_API_KEY`; para validar apenas a mecânica local sem Cohere, use
`--limit-configs 1`.

---

## Infraestrutura

| Componente | Onde roda |
|---|---|
| Pipeline de ingestão | Máquina local (IP residencial — cedoc/ bloqueia datacenters) |
| PDFs, Parquet e índices FAISS | HuggingFace Hub |
| Código-fonte | GitHub |
| Chatbot | HuggingFace Spaces |

O repositório Git contém código, configuração e documentação. Dados pesados — PDFs, Parquet e índices FAISS — ficam **fora do Git** (HuggingFace Hub).

**Exceção deliberada:** os artefatos de avaliação em `data/evaluation/` (`results*.csv`, `per_question*.json`, pareamentos, diagnósticos e auditorias) **são versionados**. São leves e funcionam como o registro reprodutível e auditável das decisões de promoção (cada fase do roadmap tem critério pré-comprometido e pareamento preservado).

---

## Como rodar

```bash
# Instalar dependências
make install

# Rodar testes
make test

# Ingestão incremental por fonte (requer HF_TOKEN no .env, IP residencial BR)
make ingest-atos           # atos normativos (Power BI + cedoc/)
make ingest-leis           # 4 leis estruturantes
make ingest-procedimentos  # PRODIST, PRORET, Regras de Transmissão
make ingest-rede           # Procedimentos de Rede (ONS)
make ingest-manuais        # manuais gov.br
make ingest-all            # todas as fontes em texto (merge incremental)

# Benchmark de extração: re-roda tudo em Markdown
make benchmark-markdown  # inclui reparo de lacunas texto/markdown + validação

# Conferir corpus publicado (Camada 1)
make validate-corpus

# Camada 2 — Processamento
make chunk-all           # gera e publica chunks (3 estratégias × 2 métodos)
make validate-chunks     # confere chunks publicados no Hub

make vectorstore-main    # vector store principal (large + article-aware + markdown)
make vectorstore-all     # matriz completa de 12 vector stores (use SKIP_EXISTING=0 para regerar)
make validate-vectorstore  # valida vector store publicada no Hub

# Camada 3.5 / 4 — RAG ponta-a-ponta
make benchmark-rag       # geração + citações + métricas LLM opcionais
```

Dataset público: [`simoesthiago/aneel-corpus`](https://huggingface.co/datasets/simoesthiago/aneel-corpus)

---

## Troubleshooting

### HuggingFace Xet bridge falha (`cas-bridge.xethub.hf.co`)

Arquivos grandes no Hub são servidos por trás do Xet content-addressed storage. Em alguns ambientes (DNS local intermitente, redes corporativas), o domínio `cas-bridge.xethub.hf.co` falha em resolver enquanto `huggingface.co` funciona normalmente. Sintoma: `requests.get` quebra com `NameResolutionError` no meio de `make benchmark-retrieval` ou de scripts de diagnóstico.

Workaround:

```bash
HF_HUB_DISABLE_XET=1 make benchmark-retrieval
```

A variável força o cliente `huggingface_hub` a usar o caminho tradicional (sem Xet). Útil também quando o cliente Xet local trava em redes restritivas. Não afeta correção dos resultados — apenas a rota de download.

### Scripts de diagnóstico (`scripts/diagnostics/`) usam cache local

A regra Hub-first do projeto vale para ingestão e publicação. **Os scripts de diagnóstico** em `scripts/diagnostics/diagnose_*.py` são exceção explícita: usam `huggingface_hub.hf_hub_download` para evitar problemas intermitentes com o Xet bridge. Isso materializa arquivos em `~/.cache/huggingface/hub/` (cache local da biblioteca, não em `data/`). É aceitável porque:

1. Os artefatos baixados são apenas para diagnóstico pontual, não fluxo oficial
2. O cache é gerenciado pela biblioteca, não versionado no repo
3. Reduz dependência da rede em diagnósticos longos
