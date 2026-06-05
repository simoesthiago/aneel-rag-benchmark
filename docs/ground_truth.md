# Ground Truth de Avaliação

O ground truth é um artefato de dados do benchmark, não código. Por isso o JSONL
local fica em `data/` e não entra no Git. O repositório versiona apenas o
contrato: schema, validação, publicação e documentação.

## Artefato Oficial

Repositório HuggingFace:

```text
simoesthiago/aneel-corpus
```

Layout:

```text
data/evaluation/ground_truth/version=retrieval-50/ground_truth.jsonl
data/evaluation/ground_truth/version=retrieval-50/manifest.json
```

Fonte local de publicação:

```text
data/evaluation/ground_truth/aneel_retrieval_50.jsonl
```

## Validação

Validação completa local, incluindo comparação com o corpus publicado:

```bash
make validate-ground-truth
```

Validação do artefato já publicado:

```bash
make validate-ground-truth-hub
```

Validação apenas de schema, sem HuggingFace:

```bash
python3 scripts/validate_ground_truth.py --schema-only
```

## Publicação

```bash
make publish-ground-truth
```

A publicação valida o arquivo antes do upload e recusa sobrescrever a versão
existente sem `--force`.

## Critérios Principais

- JSONL válido com 50 perguntas.
- IDs sequenciais `gt-0001` a `gt-0050`.
- Nenhum uso de `chunk_id`.
- `document_id`, `tipo`, `subtipo` e URL consistentes com o corpus.
- `support_excerpt` encontrado no corpus para perguntas `corpus_supported`.
- `expected_answer` sustentada pelo `support_excerpt`.
