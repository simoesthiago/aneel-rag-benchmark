# Prompt para relatório final

Use os artefatos versionados do repositório para escrever um relatório técnico
em PDF sobre o ANEEL RAG Benchmark.

## Fontes canônicas

- `README.md`: visão pública do projeto e comandos.
- `PROGRESS.md`: continuidade local e estado atual.
- `data/README.md`: contrato da pasta `data/`.
- `data/evaluation/report/tables/retrieval_matrix_v2.md`: matriz final de
  retrieval pós-H12.
- `data/evaluation/report/tables/rag_promoted_post_marco_d.md`: métricas do
  pipeline RAG promovido após Marco D.
- `data/evaluation/report/summaries/prompt_v3_pairing.md`: evidência de que o
  prompt v3 não foi promovido.
- `data/evaluation/results/diagnostic/chunking_markdown_fallback.md`:
  diagnóstico H12 do splitter markdown-aware.

## História que o relatório deve contar

1. O projeto construiu um corpus regulatório real da ANEEL e publicou dados
   pesados no Hugging Face Hub.
2. O benchmark comparou chunking, embeddings, retrieval, rerank e geração com
   métricas separadas.
3. H12 corrigiu uma incompletude das estratégias estruturais e confirmou que a
   vitória da janela fixa não era artefato.
4. O pipeline promovido permaneceu
   `large|fixed-size|texto|flat + rerank@100 + higiene`.
5. O Marco D mediu o pipeline promovido em 48 perguntas avaliáveis:
   `answer_usable=0.854`, `citation_accuracy=0.837`,
   `doc_recall@10=0.958`, `nDCG@10=0.873`.
6. Um prompt v3 com autocheck foi testado, mas não promovido
   (`saved=4`, `broken=3`, veredito `keep`).
7. As limitações devem aparecer explicitamente: corpus textual, dependência de
   APIs externas, ground truth pequeno e residuals que não devem ser escondidos.

## Regras de redação

- Não misture `doc_recall` e `nDCG` como se fossem uma única linha vencedora
  quando vierem de configurações diferentes.
- Separe fatos medidos de interpretação.
- Cite o arquivo de origem de cada tabela ou número agregado.
- Não altere métricas, ground truth ou resultados brutos durante a redação.
