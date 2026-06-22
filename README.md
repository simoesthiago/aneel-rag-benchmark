# ANEEL RAG Benchmark

Benchmark comparativo de estratégias de **Retrieval-Augmented Generation (RAG)**
sobre o corpus regulatório da ANEEL. RAG aqui significa: buscar trechos de normas
públicas, entregar esse contexto a um modelo de linguagem e medir se a resposta é
correta, citável e apoiada na fonte vigente.

> **Pergunta central:** qual combinação de extração, chunking, retrieval, rerank,
> geração e citação produz a melhor resposta regulatória — com fonte correta,
> custo aceitável e latência viável?

- **Corpus:** [`simoesthiago/aneel-corpus`](https://huggingface.co/datasets/simoesthiago/aneel-corpus) · 1643 documentos
- **Pipeline promovido:** `text-embedding-3-large | fixed-size | texto | flat + rerank@100 + higiene`
- **Estado:** ingestão, processamento, RAG e avaliação concluídos; relatório técnico final em construção

---

## Resultado atual

| Métrica | Resultado |
|---|---:|
| Respostas usáveis | **41/48** |
| `answer_usable` | **0.854** |
| `citation_accuracy` | **0.837** |
| `doc_recall@10` | **0.958** |
| `nDCG@10` | **0.873** |

Como ler o pipeline promovido:

| Termo | Significado |
|---|---|
| `fixed-size` | Divide o texto em janelas de tamanho fixo, com sobreposição |
| `texto` | Usa a extração em texto plano, não a extração em Markdown |
| `flat` | Responde com os chunks recuperados, sem substituí-los por chunks pais |
| `rerank@100` | Busca 100 candidatos no FAISS e os reordena com Cohere Rerank |
| `higiene` | Remove ruído normativo (normas revogadas, versões antigas de submódulos) |

Para auditar o resultado sem recomputar nada, comece por estes artefatos curados
(texto/CSV, custo zero de API):

- [RAG promovido](data/evaluation/report/tables/rag_promoted_post_marco_d.md) — leitura canônica
- [Matriz retrieval final](data/evaluation/report/tables/retrieval_matrix_v2.md)
- [Finalistas RAG](data/evaluation/report/tables/rag_finalists.md)
- [Replay A/B do prompt v3, não promovido](data/evaluation/report/summaries/prompt_v3_pairing.md)

---

## Corpus

Cinco famílias de documentos regulatórios. Totais consolidados da Camada 1;
linhas com `~` usam aproximação porque a contagem pública por subfonte varia com
a fonte oficial.

| Fonte | Exemplos | Docs |
|---|---|---:|
| Atos normativos | RENs, REHs, despachos e outros atos do estoque regulatório | 991 |
| Procedimentos regulatórios | PRODIST, Regras de Transmissão, PRORET | ~395 |
| Procedimentos de Rede (ONS) | Módulos e submódulos vigentes OP/RS/PR/CR/IN/RQ | ~165 |
| Manuais, modelos e instruções | Guias operacionais, modelos e planilhas públicas | 87 |
| Leis estruturantes | Leis 9.427/1996, 8.987/1995, 9.074/1995 e 13.848/2019 | 4 |
| **Total** | | **1643** |

Cada documento tem duas extrações (`texto` e `markdown`), totalizando 3286 linhas
no dataset publicado.

---

## Arquitetura

Quatro camadas que terminam em um pacote de relatório técnico auditável:

| # | Camada | Responsabilidade | Status |
|---|---|---|---|
| 1 | **Ingestão** | Coleta documentos públicos, extrai texto, valida schema e publica Parquet no Hub | Concluída |
| 2 | **Processamento** | Gera chunks, embeddings e índices FAISS | Concluída |
| 3 | **RAG** | Compara FAISS, parent-child, rerank e geração citável | Concluída |
| 4 | **Avaliação** | Mede retrieval, citação, resposta, latência e métricas com LLM opcional | Concluída |
| Final | **Relatório** | Consolida tabelas, diagnósticos, limitações e conclusões | Em construção |

**Política de artefatos:** _metodologia no Git, dado grande no Hub._ Código,
ground truth, runs leves, auditorias e tabelas ficam versionados; PDFs, Parquets
e índices FAISS vivem no Hub. Contrato completo em [data/README.md](data/README.md).

---

## Metodologia

### Extração

Cada documento é extraído em duas versões para comparar o efeito do formato de
entrada. A ferramenta concreta usada em cada arquivo fica na coluna `extrator`.

| Estratégia | Ferramentas | Coluna |
|---|---|---|
| Texto plano | PyMuPDF, BeautifulSoup, python-docx, openpyxl | `metodo_extracao="texto"` |
| Markdown estruturado | PyMuPDF4LLM, html2text, mammoth, pandas+tabulate | `metodo_extracao="markdown"` |

### Chunking

Divide documentos longos em blocos menores pesquisáveis. Três estratégias:

| Estratégia | Ideia | Resultado |
|---|---|---|
| `fixed-size` | Janelas fixas de tokens com overlap | Venceu por robustez |
| `article-aware` | Respeita artigos, seções e parágrafos | Competitivo, mas não superou `fixed-size` |
| `hierarchical-child` | Busca filhos pequenos e pode responder com o pai | Testa contexto maior para normas longas |

### Retrieval e rerank

Retrieval é a busca dos candidatos; rerank é uma segunda fase que os reordena.

| Estratégia | O que faz |
|---|---|
| Dense FAISS | Busca semântica por embeddings OpenAI |
| Hierarchical flat | Controle que busca e devolve filhos |
| Hierarchical parent-child | Busca filhos e devolve pais deduplicados |
| Cohere Rerank | Reordena candidatos FAISS antes da geração |

### Vector stores publicadas

A Camada 2 publicou **12 índices FAISS** = 2 modelos de embedding × 3 estratégias
de chunking × 2 métodos de extração:

```text
data/vectorstores/provider=openai/model=<embedding-model>/
  chunk_strategy=<strategy>/metodo_extracao=<metodo>/
    index.faiss  metadata.parquet  manifest.json
    parents.parquet   # apenas para hierarchical-child
```

As vector stores estruturais v2 ficam num repo separado
(`simoesthiago/aneel-vectorstores-h12`) para preservar intacta a matriz oficial
anterior.

---

## Métricas

| Grupo | Métricas |
|---|---|
| Retrieval | `recall_at_k`, `doc_recall_at_k`, `precision_at_k`, `mrr_at_k`, `ndcg_at_k` |
| Resposta | `citation_accuracy`, `status_accuracy`, `faithfulness`, `answer_correctness`, `answer_usable` |
| Operacional | `latency_avg`, `latency_p95`, custo por consulta, tempo de build |

Definições principais:

- **`recall_at_k`** — o trecho esperado apareceu entre os top-k resultados?
- **`doc_recall_at_k`** — o documento esperado apareceu, mesmo sem o trecho exato?
- **`nDCG@k`** — qualidade de ordenação; quanto mais cedo a evidência relevante, melhor.
- **`citation_accuracy`** — as citações da resposta apontam para evidência correta?
- **`answer_usable`** — gate composto: recuperação mínima + citação suficiente + correção suficiente.

Notas: `faithfulness` e `answer_correctness` são opcionais e só rodam com a chave
do juiz LLM — uma resposta pode ser fiel ao contexto errado, então o relatório as
lê junto com retrieval e citação. Perguntas `source_only` são rastreadas no
detalhe mas ficam fora das métricas agregadas (sem suporte textual confiável no
corpus extraído).

---

## Como reproduzir

### Setup

```bash
make install
cp -n .env.example .env
```

Os targets do `Makefile` chamam `.venv/bin/python` por padrão.

| Variável | Quando é necessária |
|---|---|
| `HF_TOKEN` | Publicar corpus, chunks, ground truth ou artefatos no Hub |
| `OPENAI_API_KEY` | Gerar embeddings OpenAI e respostas do gerador |
| `LLM_API_KEY` | Rodar juiz LLM de `faithfulness` e `answer_correctness` |
| `COHERE_API_KEY` | Rodar configs com `rerank@100` |

Sem chaves de LLM, alguns fluxos seguem em modo offline ou registram
`skipped_no_llm_key`, mas não reproduzem as métricas finais pagas.

### Checagens sem custo de API

```bash
make test lint                      # código e contratos locais
make validate-corpus                # validações contra artefatos publicados
make validate-chunks                # (exigem rede, sem custo de API paga)
make validate-vectorstore-all
```

### Rodar os benchmarks

> Estes comandos podem consumir rede, OpenAI e Cohere.

```bash
make benchmark-retrieval            # retrieval oficial sem rerank
make benchmark-retrieval-rerank     # com rerank@100; usa checkpoint para retomar
make benchmark-rag-finalists        # RAG nas configs finalistas
make benchmark-rag-capture          # captura do pipeline promovido
make benchmark-rag-replay           # replay sobre os contextos capturados
```

Cada run é gravado em `data/evaluation/runs/<modo>/<run_id>/` com `manifest.json`
registrando commit, ground truth, modelos, filtros e configuração completa.

### Recriar artefatos de base

> Use só para reconstruir ou republicar camadas. Pode ser caro e depende de rede,
> IP residencial brasileiro para algumas fontes e tokens configurados.

```bash
make ingest-all benchmark-markdown  # Camada 1 — ingestão
make chunk-all vectorstore-all      # Camada 2 — processamento
```

`make vectorstore-main` ainda existe como target histórico da Camada 2, mas não
representa o pipeline promovido atual.

---

## Infraestrutura

| Componente | Onde roda / vive |
|---|---|
| Pipeline de ingestão | Máquina local (algumas fontes bloqueiam datacenters) |
| PDFs, Parquets grandes, índices FAISS | Hugging Face Hub |
| Código-fonte | GitHub |
| Ground truth, runs pequenos, auditorias, tabelas | Git |
| Relatório final | Gerado a partir dos artefatos versionados |
</content>
</invoke>
