# Diagnósticos de avaliação

Esta pasta guarda scripts pontuais usados para investigar falhas do benchmark
de retrieval antes da Camada 3.5.

Eles são públicos porque documentam a metodologia e as hipóteses testadas, mas
não fazem parte do fluxo oficial de ingestão, chunking ou publicação. Alguns
scripts usam `huggingface_hub.hf_hub_download`, que pode criar cache em
`~/.cache/huggingface/hub/`. Esse cache não é versionado e não deve ser copiado
para `data/`.

As saídas geradas continuam em `data/evaluation/results/diagnostic/`, que é
ignorado pelo Git.
