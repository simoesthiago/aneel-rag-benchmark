# Auditoria H12 — fragmentação de chunks

Esta auditoria não reconstrói chunks, vectorstores ou embeddings.

## Shape dos chunks

| strategy | método | kind | n | <10 | <30 | p50 | p95 |
|---|---|---|---:|---:|---:|---:|---:|
| fixed-size | markdown | chunks | 14438 | 0 (0.0%) | 1 (0.0%) | 512 | 512 |
| fixed-size | texto | chunks | 14301 | 0 (0.0%) | 1 (0.0%) | 512 | 512 |
| article-aware | markdown | chunks | 84653 | 25600 (30.2%) | 51744 (61.1%) | 21 | 335 |
| article-aware | texto | chunks | 34203 | 3388 (9.9%) | 11309 (33.1%) | 52 | 800 |
| hierarchical-child | markdown | chunks | 92565 | 25600 (27.7%) | 51744 (55.9%) | 24 | 300 |
| hierarchical-child | markdown | parents | 84653 | 25600 (30.2%) | 51744 (61.1%) | 21 | 335 |
| hierarchical-child | texto | chunks | 44550 | 3388 (7.6%) | 11309 (25.4%) | 89 | 300 |
| hierarchical-child | texto | parents | 34203 | 3388 (9.9%) | 11309 (33.1%) | 52 | 800 |

## Ruído markdown em chunks <30 palavras

### fixed-size
- `outro`: 1

### article-aware
- `cabecalho_isolado`: 6912
- `fragmento_referencia_cruzada`: 2195
- `item_lista_curto`: 5699
- `marcador_imagem_omitida`: 3798
- `numero_pagina`: 2278
- `outro`: 27693
- `tabela_markdown`: 1785
- `url_footer`: 1384

### hierarchical-child
- `cabecalho_isolado`: 6912
- `fragmento_referencia_cruzada`: 2195
- `item_lista_curto`: 5699
- `marcador_imagem_omitida`: 3798
- `numero_pagina`: 2278
- `outro`: 27693
- `tabela_markdown`: 1785
- `url_footer`: 1384

## Exemplos tiny

### fixed-size / markdown
- `manual-licitacoes-e-contratos-modelo-de-formulario-de-ciencias-declaracoes-requerimentos-e-autorizacoes::markdown::fixed-size::0000` (14 palavras, outro): **_MODELO DE DOCUMENTO_** ** _FORMULÁRIO DE CIÊNCIAS, DECLARAÇÕES, REQUERIMENTOS E AUTORIZAÇÕES– COLABORADORES DO CONTRATADO_**

### fixed-size / texto
- `manual-licitacoes-e-contratos-modelo-de-formulario-de-ciencias-declaracoes-requerimentos-e-autorizacoes::texto::fixed-size::0000` (13 palavras, cabecalho_isolado): MODELO DE DOCUMENTO FORMULÁRIO DE CIÊNCIAS, DECLARAÇÕES, REQUERIMENTOS E AUTORIZAÇÕES– COLABORADORES DO CONTRATADO

### article-aware / markdown
- `manual-air-modelo-de-air-srm-leilao-ee-roraima::markdown::article-aware::0007` (1 palavras, cabecalho_isolado): 48547.001672/2019-00
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::article-aware::0012` (1 palavras, outro): Exemplo:
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::article-aware::0018` (1 palavras, outro): ______________________________
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::article-aware::0024` (1 palavras, outro): Exemplo:
- `manual-distribuicao-manual-de-instrucoes-da-base-de-dados-de-ocorrencias-e-interrupcoes-da-distribui::markdown::article-aware::0005` (1 palavras, outro): 1

### article-aware / texto
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::article-aware::0007` (1 palavras, cabecalho_isolado): SUMÁRIO
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::article-aware::0013` (1 palavras, outro): Exemplo:
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::article-aware::0029` (1 palavras, outro): “APLGEO9999OPERACAO_MMAAAA_S999.rar”
- `manual-distribuicao-manual-de-instrucoes-para-envio-de-dados-referentes-ao-primeiro-nivel-de-tratame-2::texto::article-aware::0000` (1 palavras, outro): 1
- `manual-distribuicao-manual-de-instrucoes-para-envio-de-dados-referentes-ao-primeiro-nivel-de-tratame-2::texto::article-aware::0041` (1 palavras, outro): 103

### hierarchical-child / markdown
- `manual-air-modelo-de-air-srm-leilao-ee-roraima::markdown::hierarchical-child::0007` (1 palavras, cabecalho_isolado): 48547.001672/2019-00
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::hierarchical-child::0012` (1 palavras, outro): Exemplo:
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::hierarchical-child::0019` (1 palavras, outro): ______________________________
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::markdown::hierarchical-child::0025` (1 palavras, outro): Exemplo:
- `manual-distribuicao-manual-de-instrucoes-da-base-de-dados-de-ocorrencias-e-interrupcoes-da-distribui::markdown::hierarchical-child::0005` (1 palavras, outro): 1

### hierarchical-child / texto
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::hierarchical-child::0007` (1 palavras, cabecalho_isolado): SUMÁRIO
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::hierarchical-child::0013` (1 palavras, outro): Exemplo:
- `manual-cartografia-e-geoprocessamento-manual-para-registro-dos-arquivos-cartograficos-areas-de-concessao::texto::hierarchical-child::0030` (1 palavras, outro): “APLGEO9999OPERACAO_MMAAAA_S999.rar”
- `manual-distribuicao-manual-de-instrucoes-para-envio-de-dados-referentes-ao-primeiro-nivel-de-tratame-2::texto::hierarchical-child::0000` (1 palavras, outro): 1
- `manual-distribuicao-manual-de-instrucoes-para-envio-de-dados-referentes-ao-primeiro-nivel-de-tratame-2::texto::hierarchical-child::0042` (1 palavras, outro): 103

## Documento certo sem trecho certo

Casos em que `doc_recall_at_k = 1` e `recall_at_k = 0`.

- `text-embedding-3-large|article-aware|markdown|flat`: 19 perguntas (gt-0002, gt-0009, gt-0015, gt-0016, gt-0019, gt-0020, gt-0021, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0032, gt-0034, gt-0035, gt-0036, gt-0037, gt-0039, gt-0041)
- `text-embedding-3-large|hierarchical-child|markdown|flat`: 18 perguntas (gt-0002, gt-0009, gt-0015, gt-0016, gt-0019, gt-0020, gt-0021, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0034, gt-0035, gt-0036, gt-0037, gt-0039, gt-0041)
- `text-embedding-3-large|hierarchical-child|markdown|hierarchical`: 18 perguntas (gt-0002, gt-0009, gt-0015, gt-0016, gt-0019, gt-0020, gt-0021, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0034, gt-0035, gt-0036, gt-0037, gt-0039, gt-0041)
- `text-embedding-3-large|article-aware|texto|flat`: 10 perguntas (gt-0002, gt-0009, gt-0010, gt-0021, gt-0025, gt-0027, gt-0029, gt-0033, gt-0036, gt-0037)
- `text-embedding-3-large|hierarchical-child|texto|flat`: 13 perguntas (gt-0002, gt-0009, gt-0010, gt-0019, gt-0021, gt-0023, gt-0024, gt-0027, gt-0029, gt-0034, gt-0036, gt-0037, gt-0042)
- `text-embedding-3-large|hierarchical-child|texto|hierarchical`: 11 perguntas (gt-0002, gt-0009, gt-0010, gt-0019, gt-0021, gt-0027, gt-0029, gt-0034, gt-0036, gt-0037, gt-0042)
- `text-embedding-3-small|article-aware|markdown|flat`: 15 perguntas (gt-0002, gt-0006, gt-0010, gt-0016, gt-0018, gt-0020, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0035, gt-0036, gt-0037, gt-0041)
- `text-embedding-3-small|hierarchical-child|markdown|flat`: 18 perguntas (gt-0002, gt-0006, gt-0010, gt-0015, gt-0016, gt-0018, gt-0020, gt-0021, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0035, gt-0036, gt-0037, gt-0041, gt-0047)
- `text-embedding-3-small|hierarchical-child|markdown|hierarchical`: 17 perguntas (gt-0002, gt-0006, gt-0010, gt-0015, gt-0016, gt-0018, gt-0020, gt-0021, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0035, gt-0036, gt-0037, gt-0041)
- `text-embedding-3-small|article-aware|texto|flat`: 9 perguntas (gt-0002, gt-0006, gt-0007, gt-0010, gt-0019, gt-0029, gt-0035, gt-0036, gt-0037)
- `text-embedding-3-small|hierarchical-child|texto|flat`: 14 perguntas (gt-0002, gt-0006, gt-0010, gt-0019, gt-0020, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0034, gt-0036, gt-0037, gt-0042)
- `text-embedding-3-small|hierarchical-child|texto|hierarchical`: 11 perguntas (gt-0002, gt-0006, gt-0010, gt-0019, gt-0020, gt-0025, gt-0029, gt-0034, gt-0036, gt-0037, gt-0042)
- `text-embedding-3-large|article-aware|markdown|flat+rerank`: 14 perguntas (gt-0002, gt-0010, gt-0015, gt-0016, gt-0020, gt-0022, gt-0023, gt-0024, gt-0025, gt-0034, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-large|hierarchical-child|markdown|flat+rerank`: 15 perguntas (gt-0002, gt-0010, gt-0015, gt-0016, gt-0020, gt-0022, gt-0023, gt-0024, gt-0025, gt-0029, gt-0034, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-large|hierarchical-child|markdown|hierarchical+rerank`: 14 perguntas (gt-0002, gt-0010, gt-0015, gt-0016, gt-0020, gt-0022, gt-0023, gt-0024, gt-0025, gt-0034, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-large|article-aware|texto|flat+rerank`: 8 perguntas (gt-0002, gt-0010, gt-0019, gt-0025, gt-0029, gt-0036, gt-0037, gt-0049)
- `text-embedding-3-large|hierarchical-child|texto|flat+rerank`: 12 perguntas (gt-0002, gt-0009, gt-0010, gt-0019, gt-0025, gt-0029, gt-0033, gt-0034, gt-0036, gt-0037, gt-0042, gt-0049)
- `text-embedding-3-large|hierarchical-child|texto|hierarchical+rerank`: 9 perguntas (gt-0002, gt-0010, gt-0019, gt-0025, gt-0029, gt-0034, gt-0036, gt-0037, gt-0049)
- `text-embedding-3-small|article-aware|markdown|flat+rerank`: 13 perguntas (gt-0002, gt-0007, gt-0010, gt-0015, gt-0016, gt-0020, gt-0023, gt-0024, gt-0025, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-small|hierarchical-child|markdown|flat+rerank`: 13 perguntas (gt-0002, gt-0007, gt-0010, gt-0016, gt-0020, gt-0023, gt-0024, gt-0025, gt-0029, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-small|hierarchical-child|markdown|hierarchical+rerank`: 12 perguntas (gt-0002, gt-0007, gt-0010, gt-0016, gt-0020, gt-0023, gt-0024, gt-0025, gt-0036, gt-0037, gt-0041, gt-0049)
- `text-embedding-3-small|article-aware|texto|flat+rerank`: 12 perguntas (gt-0002, gt-0006, gt-0007, gt-0010, gt-0019, gt-0020, gt-0025, gt-0029, gt-0036, gt-0037, gt-0042, gt-0049)
- `text-embedding-3-small|hierarchical-child|texto|flat+rerank`: 11 perguntas (gt-0002, gt-0006, gt-0007, gt-0010, gt-0019, gt-0025, gt-0029, gt-0036, gt-0037, gt-0042, gt-0049)
- `text-embedding-3-small|hierarchical-child|texto|hierarchical+rerank`: 10 perguntas (gt-0002, gt-0006, gt-0007, gt-0010, gt-0019, gt-0025, gt-0029, gt-0036, gt-0037, gt-0049)

## Texto vs markdown

Markdown lidera doc_recall no retrieval puro, mas texto vence o gate RAG por citation_accuracy e answer_usable_rate. A auditoria deve tratar essas conclusões como métricas diferentes.

### Retrieval puro — fixed-size + rerank

| método | recall | doc_recall | MRR | nDCG |
|---|---:|---:|---:|---:|
| markdown | 0.958 | 0.979 | 0.875 | 0.867 |
| texto | 0.958 | 0.958 | 0.898 | 0.872 |

### RAG finalistas — fixed-size + rerank

| método | usable | citation | correctness | doc_recall |
|---|---:|---:|---:|---:|
| markdown | 0.771 | 0.723 | 0.915 | 0.979 |
| texto | 0.812 | 0.773 | 0.922 | 0.958 |
