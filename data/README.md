# Contrato da pasta `data/`

> Congelado no **Marco A** do roadmap (`PROGRESS.md`). Objetivo: separar com
> clareza **entrada canônica**, **run bruto**, **auditoria** e **material de
> relatório**, para que os próximos benchmarks grandes não voltem a poluir a
> estrutura. Leia este arquivo antes de gravar qualquer artefato novo em
> `data/`.

## Princípio Hub-first

O Git guarda **código, configuração, documentação e artefatos de avaliação
leves** (ground truth pequeno, CSVs agregados, manifestos, auditorias). Os
**dados grandes ficam no Hugging Face Hub**, nunca no Git:

- PDFs, Parquets, índices FAISS, dumps brutos → **Hub** (`simoesthiago/aneel-corpus`).
- `data/documentos_corpus.csv`, `data/chunks/`, `data/vectorstores/`, `data/raw/`
  → **gitignored** (ver `.gitignore`); são materializados localmente ou lidos do Hub.
- Vector stores **v2 das estratégias estruturais** (parser/splitter de chunking
  corrigidos — H12) ficam num repo separado, `simoesthiago/aneel-vectorstores-h12`,
  para preservar intactas as v1 do Marco B em `aneel-corpus`. Comparativo em
  `data/evaluation/report/tables/retrieval_matrix_v2.*`.

Regra prática em caso de dúvida: **metodologia no Git, dado grande no Hub.**

## Layout

```text
data/
  documentos_corpus.csv         # (gitignored) corpus materializado local; fonte = Hub
  evaluation/
    ground_truth/               # ENTRADA CANÔNICA — pequena e versionável
      aneel_retrieval_50.jsonl
    runs/                       # RUN BRUTO — saída de benchmark, 1 pasta por run
      retrieval/<run_id>/
      rag/<run_id>/
      manifest.template.json    # contrato/schema do manifest.json (não é um run)
    report/                     # MATERIAL DE RELATÓRIO — limpo, pronto para o PDF
      tables/
      figures/
      summaries/
    audit/                      # AUDITORIA — raciocínio, decisões, diagnósticos
    cache/                      # (gitignored) cache de embeddings de query
    results/                    # HISTÓRICO pré-contrato (ver "Artefatos históricos")
```

## As quatro classes de artefato

### 1. Entrada canônica — `ground_truth/`

O ground truth é a **fonte de verdade pequena e versionável** do benchmark.
Aponta para **evidência estável** (documento/trecho oficial), nunca para
`chunk_id` — porque `chunk_id` muda entre estratégias de chunking e enviesaria
a comparação. A versão vigente é `retrieval-50-v2` (publicada também no Hub em
`data/evaluation/ground_truth/version=retrieval-50-v2/`).

**Regra dura:** o GT só muda **com proveniência** (fonte oficial verificável).
Nunca se edita o GT para "passar no teste".

### 2. Run bruto — `runs/`

Saída crua de cada execução de benchmark. **Cada run vive em sua própria pasta
timestampada** `runs/<mode>/<run_id>/`, então um run nunca sobrescreve outro.

`<run_id>` = `<timestamp_utc>-<commit_curto>[-dirty]` (ex.:
`20260612T143000Z-9b3fe6f`). Gerado por `src/evaluation/run_manifest.py`.
`dirty=false` significa que não havia alterações rastreadas nem arquivos novos
relevantes fora do Git; arquivos novos criados pelo próprio run em
`data/evaluation/runs/` e cache em `data/evaluation/cache/` não contam como
sujeira.

Cada run contém:

| arquivo | conteúdo |
|---|---|
| `manifest.json` | **obrigatório** — config completa, GT, commit, modelos, filtros, métricas, paths (ver `manifest.template.json`) |
| `results.csv` | tabela agregada por configuração |
| `per_question.json` | detalhe por pergunta |
| `failure_analysis.{json,md}` | (modo RAG) diagnóstico de usabilidade |

Um `results.csv` solto não diz qual GT, commit ou filtros o geraram — por isso
**todo run carrega um `manifest.json`**. Runs são gerados por
`scripts/run_benchmark.py` (via `make benchmark-retrieval` / `make benchmark-rag`).

### Checkpoint e replay

`--checkpoint` pode ser usado para retomar benchmarks caros sem repetir chamadas
OpenAI/Cohere. Cada linha do checkpoint carrega uma assinatura da execução:
modo, `top_k`, hash das perguntas avaliadas, config completa, commit, estado
dirty, modelos e versão/fonte do ground truth. Um registro só é reaproveitado
quando essa assinatura bate exatamente; checkpoints antigos ou incompatíveis são
ignorados com aviso.

No modo RAG, `--replay-contexts` congela o retrieval a partir de um sidecar de
contextos capturados. Replay é estrito: se alguma pergunta avaliável não existir
no sidecar, o run falha cedo em vez de tratar a ausência como "sem contexto".

### 3. Auditoria — `audit/`

Onde mora o **raciocínio**: por que cada decisão de promoção foi tomada,
diagnósticos de causa-raiz, planos e conclusões de auditoria externa. É o que
explica a metodologia no relatório. Conteúdo textual, versionado.
Fonte principal de continuidade: `audit/ROADMAP.md`.

### 4. Material de relatório — `report/`

Tabelas, figuras e sínteses **limpas e prontas para o PDF final**. Diferente de
`runs/` (cru) e `audit/` (raciocínio): aqui só entra o que já está curado para
publicação. Preenchido a partir do Marco B em diante.

- `tables/` — tabelas comparativas (matriz retrieval, finalistas RAG, ablations).
- `figures/` — gráficos.
- `summaries/` — sínteses textuais.

## O que vai (e o que não vai) para o Git

**Vai para o Git** (leve, auditável, reprodutível):

- código, testes, scripts de diagnóstico, documentação;
- ground truth pequeno (`ground_truth/`);
- runs de benchmark (`runs/`): `manifest.json`, `results.csv`, `per_question.json`,
  `failure_analysis.*` — são texto/CSV/JSON na escala de KB–MB;
- auditorias (`audit/`) e material de relatório (`report/`).

**Não vai para o Git** (ver `.gitignore`):

- PDFs, Parquets, índices FAISS (`*.pdf`, `*.parquet`, `*.faiss`);
- corpus materializado (`data/documentos_corpus.csv`), `data/chunks/`,
  `data/vectorstores/`, `data/raw/`;
- cache de embeddings de query (`data/evaluation/cache/`).

> Higiene futura: `runs/` acumula uma pasta por execução. Quando houver muitos
> runs redundantes, **podar os antigos** mantendo os canônicos (os promovidos ao
> `report/`) — não versionar dezenas de `per_question.json` repetidos.

## Artefatos históricos — `results/`

`data/evaluation/results/` (`rag-50/`, `retrieval-50/`, `diagnostic/`) é o
**registro pré-contrato**, anterior ao Marco A. Ele é **fonte única de
evidência** de várias decisões já tomadas (Fases F1–F1.5 do roadmap) e é
referenciado por `PROGRESS.md` e `audit/ROADMAP.md`. Por isso **permanece no
lugar, intocado**, até que o Marco B/C regenere a matriz oficial em `runs/` e
promova os números canônicos para `report/`.

Enquanto isso:

- **Leitura canônica atual** do RAG: `results/rag-50/` (35/48 usáveis,
  `doc_recall=0.979`).
- **Runs novos** (a partir de agora) vão para `runs/`, não para `results/`.
- Nada em `results/` deve ser movido ou apagado sem antes confirmar que não é
  a única evidência de uma decisão.
