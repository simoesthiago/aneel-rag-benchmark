# ANEEL RAG Benchmark

Benchmark comparativo de estratégias de **Retrieval-Augmented Generation
(RAG)** aplicadas ao ecossistema regulatório da ANEEL.

RAG, neste projeto, significa: buscar trechos de normas públicas, entregar esse
contexto a um modelo de linguagem e medir se a resposta final é correta,
citável e apoiada na fonte vigente.

> Qual combinação de extração, chunking, retrieval, rerank, geração e citação
> normativa produz a melhor resposta regulatória com fonte correta, custo
> aceitável e latência viável?

---

## Resultado atual

O pipeline promovido depois do Marco D é:

```text
text-embedding-3-large | fixed-size | texto | flat + rerank@100 + higiene
```

Leitura dos termos:

- `fixed-size`: divide o texto em janelas de tamanho fixo, com sobreposição.
- `texto`: usa a extração em texto plano, não a extração em Markdown.
- `flat`: busca diretamente nos chunks recuperados, sem substituir por chunks
  pais.
- `rerank@100`: primeiro busca 100 candidatos no FAISS, depois reordena com
  Cohere Rerank.
- `higiene`: remove ruídos normativos que não devem competir com a fonte
  vigente, como normas revogadas e versões antigas de submódulos.

Resultado canônico do Marco D:

| Métrica | Resultado |
|---|---:|
| Respostas usáveis | **41/48** |
| `answer_usable` | **0.854** |
| `citation_accuracy` | **0.837** |
| `doc_recall@10` | **0.958** |
| `nDCG@10` | **0.873** |

Arquivos rastreáveis:

- [RAG promovido pós-Marco D](data/evaluation/report/tables/rag_promoted_post_marco_d.md)
- [Matriz retrieval final pós-H12](data/evaluation/report/tables/retrieval_matrix_v2.md)
- [Replay A/B do prompt v3, não promovido](data/evaluation/report/summaries/prompt_v3_pairing.md)

Estado do projeto:

- Marcos A-D concluídos: contrato de `data/`, matriz retrieval, finalistas RAG
  e melhoria final de citação.
- Marco E cancelado por decisão de escopo: este repositório não termina em uma
  interface; termina em benchmark e relatório técnico.
- Marco F em andamento: consolidar pacote final de evidências e relatório.

---

## Escopo do corpus

O corpus cobre cinco famílias de documentos regulatórios. Os totais abaixo são
os números consolidados da Camada 1; algumas linhas usam aproximação porque a
contagem pública por subfonte pode variar com a fonte oficial.

| Fonte | Exemplos | Docs |
|---|---|---:|
| Atos normativos | RENs, REHs, despachos e outros atos do estoque regulatório | 991 |
| Procedimentos regulatórios | PRODIST, Regras de Transmissão, PRORET | ~395 |
| Procedimentos de Rede (ONS) | Módulos e submódulos vigentes OP/RS/PR/CR/IN/RQ | ~165 |
| Manuais, modelos e instruções | Guias operacionais, modelos e planilhas públicas | 87 |
| Leis estruturantes | Leis 9.427/1996, 8.987/1995, 9.074/1995 e 13.848/2019 | 4 |
| **Total** | | **1643** |

Cada documento tem duas extrações no Hub, `texto` e `markdown`, totalizando
3286 linhas no corpus publicado.

Dataset público: [`simoesthiago/aneel-corpus`](https://huggingface.co/datasets/simoesthiago/aneel-corpus)

---

## Arquitetura e artefatos

O pipeline tem 4 camadas e termina em um pacote de relatório técnico auditável:

| # | Camada | Responsabilidade | Status |
|---|---|---|---|
| 1 | **Ingestão** | Coleta documentos públicos, extrai texto, valida schema e publica Parquet no Hugging Face Hub | Concluída |
| 2 | **Processamento** | Gera chunks, embeddings e índices FAISS | Concluída |
| 3 | **RAG** | Compara busca FAISS, parent-child, rerank e geração citável | Concluída |
| 4 | **Avaliação** | Mede retrieval, citação, resposta, latência e métricas com LLM opcional | Concluída |
| Final | **Relatório** | Consolida tabelas, diagnósticos, limitações e conclusões | Em construção |

Arquivos de orientação:

| Arquivo | Papel |
|---|---|
| [PROGRESS.md](PROGRESS.md) | Estado atual e próximos passos; leia primeiro ao retomar trabalho |
| [data/README.md](data/README.md) | Contrato da pasta `data/`: o que é entrada, run bruto, auditoria e relatório |
| [DECISIONS.md](DECISIONS.md) | Registro do porquê das decisões arquiteturais |
| [docs/schema.md](docs/schema.md) | Schema do corpus, chunks e artefatos derivados |

O Git guarda código, configuração, documentação e artefatos leves de avaliação.
Dados pesados - PDFs, Parquets grandes e índices FAISS - ficam no Hugging Face
Hub.

---

## Metodologia

### Extração

Cada documento é extraído em duas versões para comparar o efeito do formato de
entrada:

| Estratégia | Ferramentas principais | Coluna |
|---|---|---|
| Texto plano | PyMuPDF, BeautifulSoup, python-docx, openpyxl | `metodo_extracao="texto"` |
| Markdown estruturado | PyMuPDF4LLM, html2text, mammoth, pandas+tabulate | `metodo_extracao="markdown"` |

A ferramenta concreta usada em cada arquivo fica registrada na coluna
`extrator`.

### Chunking

Chunking é a etapa que divide documentos longos em blocos menores pesquisáveis.
O benchmark compara três estratégias:

| Estratégia | Ideia | Observação |
|---|---|---|
| `fixed-size` | Janelas fixas de tokens com overlap | Venceu por robustez no resultado final |
| `article-aware` | Tenta respeitar artigos, seções e parágrafos | Melhorou após H12, mas não superou `fixed-size` |
| `hierarchical-child` | Busca filhos pequenos e pode responder com o pai | Testa contexto maior para normas longas |

### Retrieval e rerank

Retrieval é a busca dos trechos candidatos. Rerank é uma segunda fase que
reordena candidatos já encontrados.

| Estratégia | O que mede |
|---|---|
| Dense FAISS | Busca semântica por embeddings OpenAI |
| Hierarchical flat | Controle que busca e devolve filhos |
| Hierarchical parent-child | Busca filhos e devolve pais deduplicados |
| Cohere Rerank | Reordenação de candidatos FAISS antes da geração |

### Vector stores publicadas

A Camada 2 publicou 12 índices FAISS no Hub:

```text
2 modelos de embedding x 3 estratégias de chunking x 2 métodos de extração
```

Layout dos pacotes:

```text
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

As vector stores estruturais v2 do diagnóstico H12 ficam em um repo separado
(`simoesthiago/aneel-vectorstores-h12`) para preservar intacta a matriz oficial
anterior.

---

## Como reproduzir

### Pré-requisitos

Use os targets do `Makefile`; eles chamam `.venv/bin/python` por padrão.

```bash
make install
cp -n .env.example .env
```

Variáveis de ambiente:

| Variável | Quando é necessária |
|---|---|
| `HF_TOKEN` | Publicar corpus, chunks, ground truth ou artefatos no Hugging Face Hub |
| `OPENAI_API_KEY` | Gerar embeddings OpenAI e respostas do gerador |
| `LLM_API_KEY` | Rodar juiz LLM de `faithfulness` e `answer_correctness` |
| `COHERE_API_KEY` | Rodar configs com `rerank@100` |

Sem chaves de LLM, alguns fluxos continuam em modo offline ou registram status
como `skipped_no_llm_key`, mas não reproduzem as métricas finais pagas.

### Checagens baratas

Estas checagens validam código e contratos locais. Elas não reconstroem o
corpus nem os índices.

```bash
make test
make lint
```

Validações contra artefatos publicados exigem rede, mas não devem gerar custo
de API paga:

```bash
make validate-corpus
make validate-chunks
make validate-vectorstore-all
```

### Ler os resultados sem recomputar

Para auditar o resultado final, comece pelos artefatos curados:

```text
data/evaluation/report/tables/retrieval_matrix_v2.md
data/evaluation/report/tables/rag_finalists.md
data/evaluation/report/tables/rag_promoted_post_marco_d.md
data/evaluation/report/summaries/prompt_v3_pairing.md
```

Esses arquivos são o caminho certo para entender o benchmark sem gastar com
OpenAI ou Cohere.

### Reproduzir benchmarks

Estes comandos podem consumir rede, OpenAI e Cohere:

```bash
# Retrieval oficial sem rerank
make benchmark-retrieval

# Retrieval oficial com rerank@100; usa checkpoint para retomar sem regastar
make benchmark-retrieval-rerank

# RAG nos finalistas do Marco C
make benchmark-rag-finalists

# Captura e replay do pipeline promovido usados no Marco D
make benchmark-rag-capture
make benchmark-rag-replay
```

Os runs novos são gravados em `data/evaluation/runs/<modo>/<run_id>/` com
`manifest.json`. O manifesto registra commit, ground truth, modelos, filtros e
configuração completa.

### Recriar artefatos de base

Use estes comandos só quando a intenção for reconstruir ou republicar camadas.
Eles podem ser caros e dependem de rede, IP residencial brasileiro para algumas
fontes e tokens configurados.

```bash
# Camada 1 - ingestão
make ingest-atos
make ingest-leis
make ingest-procedimentos
make ingest-rede
make ingest-manuais
make ingest-all
make benchmark-markdown

# Camada 2 - processamento
make chunk-all
make vectorstore-all
```

`make vectorstore-main` ainda existe como target histórico de Camada 2, mas não
representa o pipeline promovido atual. Para ler o resultado final, use os
arquivos em `data/evaluation/report/`.

---

## Métricas

| Grupo | Métricas |
|---|---|
| Retrieval | `recall_at_k`, `doc_recall_at_k`, `precision_at_k`, `mrr_at_k`, `ndcg_at_k` |
| Resposta | `citation_accuracy`, `status_accuracy`, `faithfulness`, `answer_correctness`, `answer_usable` |
| Operacional | `latency_avg`, `latency_p95`, custo por consulta e tempo de build |

Definições principais:

- `recall_at_k`: mede se o trecho esperado apareceu entre os top-k resultados.
- `doc_recall_at_k`: mede se o documento esperado apareceu, mesmo que o trecho
  exato não tenha sido recuperado.
- `nDCG@k`: mede qualidade de ordenação; quanto mais cedo aparece evidência
  relevante, melhor.
- `citation_accuracy`: mede se as citações usadas na resposta apontam para
  evidência correta.
- `answer_usable`: gate composto. Uma resposta é usável quando tem recuperação
  mínima, citação suficiente e correção de resposta suficiente.

Perguntas `source_only` ficam rastreadas no detalhe, mas não entram nas métricas
agregadas porque não têm suporte textual confiável no corpus extraído.

`faithfulness` e `answer_correctness` são opcionais e rodam apenas quando a
chave do juiz LLM está configurada. Uma resposta pode ser fiel ao contexto
errado; por isso o relatório lê essas métricas junto com retrieval e citação.

---

## Infraestrutura e política de artefatos

| Componente | Onde roda ou vive |
|---|---|
| Pipeline de ingestão | Máquina local, porque algumas fontes bloqueiam datacenters |
| PDFs, Parquets grandes e índices FAISS | Hugging Face Hub |
| Código-fonte | GitHub |
| Ground truth, runs pequenos, auditorias e tabelas | Git |
| Relatório final | Gerado a partir dos artefatos versionados |

Regra prática:

```text
metodologia no Git, dado grande no Hub
```

Exceção deliberada: artefatos leves de avaliação em `data/evaluation/` são
versionados porque registram as decisões de promoção. O contrato completo está
em [data/README.md](data/README.md).

---

## Troubleshooting

### Hugging Face Xet bridge falha (`cas-bridge.xethub.hf.co`)

Arquivos grandes no Hub podem passar pelo Xet content-addressed storage. Em
algumas redes, `cas-bridge.xethub.hf.co` falha enquanto `huggingface.co`
continua funcionando. Sintoma típico: `NameResolutionError` no meio de
`make benchmark-retrieval` ou de scripts de diagnóstico.

Workaround:

```bash
HF_HUB_DISABLE_XET=1 make benchmark-retrieval
```

Isso muda a rota de download, não a correção dos resultados.

### Scripts de diagnóstico usam cache local

A regra Hub-first vale para ingestão e publicação. Alguns scripts em
`scripts/diagnostics/` usam `huggingface_hub.hf_hub_download` para reduzir
falhas intermitentes de rede. Isso materializa arquivos em
`~/.cache/huggingface/hub/`, que é cache gerenciado pela biblioteca e não é
versionado no repositório.

Essa exceção é aceitável porque os artefatos baixados são usados apenas para
diagnóstico pontual, não como fonte canônica do projeto.
