# Histograma de comprimento de chunks (palavras)

Limite de risco de truncamento: 6000 palavras (~8000 tokens BPE, abaixo de 8191 do embedder OpenAI)

| model                  | strategy           | metodo   | kind            |     n |   min |   p50 |   p95 |   p99 |   max |   above_6000_words |
|:-----------------------|:-------------------|:---------|:----------------|------:|------:|------:|------:|------:|------:|-------------------:|
| text-embedding-3-large | fixed-size         | markdown | chunks (filhos) | 14438 |    14 |   512 |   512 |   512 |   512 |                  0 |
| text-embedding-3-large | fixed-size         | texto    | chunks (filhos) | 14301 |    13 |   512 |   512 |   512 |   512 |                  0 |
| text-embedding-3-large | article-aware      | markdown | chunks (filhos) | 84653 |     1 |    21 |   335 |   800 |   800 |                  0 |
| text-embedding-3-large | article-aware      | texto    | chunks (filhos) | 34203 |     1 |    52 |   800 |   800 |   800 |                  0 |
| text-embedding-3-large | hierarchical-child | markdown | chunks (filhos) | 92565 |     1 |    24 |   300 |   300 |   300 |                  0 |
| (shared)               | hierarchical-child | markdown | parents         | 84653 |     1 |    21 |   335 |   800 |   800 |                  0 |
| text-embedding-3-large | hierarchical-child | texto    | chunks (filhos) | 44550 |     1 |    89 |   300 |   300 |   300 |                  0 |
| (shared)               | hierarchical-child | texto    | parents         | 34203 |     1 |    52 |   800 |   800 |   800 |                  0 |
| text-embedding-3-small | fixed-size         | markdown | chunks (filhos) | 14438 |    14 |   512 |   512 |   512 |   512 |                  0 |
| text-embedding-3-small | fixed-size         | texto    | chunks (filhos) | 14301 |    13 |   512 |   512 |   512 |   512 |                  0 |
| text-embedding-3-small | article-aware      | markdown | chunks (filhos) | 84653 |     1 |    21 |   335 |   800 |   800 |                  0 |
| text-embedding-3-small | article-aware      | texto    | chunks (filhos) | 34203 |     1 |    52 |   800 |   800 |   800 |                  0 |
| text-embedding-3-small | hierarchical-child | markdown | chunks (filhos) | 92565 |     1 |    24 |   300 |   300 |   300 |                  0 |
| text-embedding-3-small | hierarchical-child | texto    | chunks (filhos) | 44550 |     1 |    89 |   300 |   300 |   300 |                  0 |
