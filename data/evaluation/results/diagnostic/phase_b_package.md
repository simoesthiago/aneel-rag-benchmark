# Fase B — Pacote de Inspeção Manual

Para cada pergunta abaixo, abra o PDF do documento ESPERADO e responda às perguntas no final de cada seção. As respostas vão informar quais das hipóteses H4 (dupla resposta), H6 (vocabulário) ou H11 (versão errada) explicam a falha.

**Config usada:** text-embedding-3-large + fixed-size + markdown + flat (a melhor da matriz, recall@10=0.77 / doc_recall@10=0.854).


---

## gt-0002

**Pergunta:** Para fins da REN 1000/2021, o que são bandeiras tarifárias?

**Resposta esperada (GT):** São um sistema aplicado por meio da tarifa de energia com a finalidade de sinalizar aos consumidores os custos atuais da geração de energia elétrica.

### Fonte esperada (ground truth)

**Fonte #1**
- `document_id`: `ren-2021-1000`
- Título: Estabelece as Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica; revoga as Resoluções Normativas ANEEL nº 414, de 9 de setembro de 2010; nº 470, de 13 de dezembro de 2011; nº 901, de 8 de dezembro de 2020 e dá outras providências.
- Citação: REN 1000/2021, Art. 2º
- Section label: `Art. 2º, definição de bandeiras tarifárias`
- URL: https://www2.aneel.gov.br/cedoc/bren20211000.pdf
- Support excerpt: > bandeiras tarifárias: sistema que tem como finalidade sinalizar os custos atuais da geração de energia elétrica ao consumidor por meio da tarifa de energia.
- Posição no retrieval: ****doc não aparece nem no top-100****

### Top-10 chunks devolvidos pela melhor config (o que o sistema achou que era relevante)

| rank | document_id | titulo | texto (preview) |
|---:|---|---|---|
| 1 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-9c-aren20221003` | PRORET — Proret Submod 6.8 V 1.9C aren20221003 | ## **ANEXO L** **Módulo 6.8: Bandeiras Tarifárias** **Submódulo 6.8** **BANDEIRAS TARIFÁRIAS** **Versão 1.9 C** ## **1. OBJETIVO** 1. Estabelecer as definições, metodologias e proc ... |
| 2 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-10c-aren20241084` | PRORET — Proret Submod 6.8 V 1.10C aren20241084 | ## **ANEXO L** **Módulo 6.8: Bandeiras Tarifárias** **Submódulo 6.8** **BANDEIRAS TARIFÁRIAS** **Versão 1.10 C** ## **1. OBJETIVO** 1. Estabelecer as definições, metodologias e pro ... |
| 3 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-9-aren2020883` | PRORET — Proret Submod 6.8 V 1.9 aren2020883 | - A. Sinalizar aos consumidores as condições de geração de energia elétrica no SIN, por meio da cobrança de valor adicional à Tarifa de Energia – TE; e - B. Equalizar parcela de cu ... |
| 4 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-9-aren2020883` | PRORET — Proret Submod 6.8 V 1.9 aren2020883 | **==> picture [65 x 78] intentionally omitted <==** ## A G Ê N C I A N A C I O N A L D E E N E R G I A E L É T R I C A ## **Módulo 6.8: Bandeiras Tarifárias** ## **S u b m ó d u l  ... |
| 5 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-1-aren2015689` | PRORET — Proret Submod 6.8 V 1.1 aren2015689 | como as faixas de acionamento, para cada ano civil, a partir da previsão dos custos relativos à geração de energia por fonte termelétrica e exposições ao mercado de curto prazo que ... |
| 6 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-2-aren2015694` | PRORET — Proret Submod 6.8 V 1.2 aren2015694 | das Bandeiras Tarifárias Amarela e Vermelha, bem como as faixas de acionamento, para cada ano civil, a partir da previsão dos custos relativos à geração de energia por fonte termel ... |
| 7 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-10c-aren20241084` | PRORET — Proret Submod 6.8 V 1.10C aren20241084 | custos realizados da geração de energia por fonte termelétrica e das exposições ao mercado de curto prazo, apurados pela CCEE conforme Regras de Comercialização e Mecanismo Auxilia ... |
| 8 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-9c-aren20221003` | PRORET — Proret Submod 6.8 V 1.9C aren20221003 | geração de energia por fonte termelétrica e das exposições ao mercado de curto prazo, apurados pela CCEE conforme Regras de Comercialização e Mecanismo Auxiliar de Cálculo – MAC. 1 ... |
| 9 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-0-aren2015649` | PRORET — Proret Submod 6.8 V 1.0 aren2015649 | energia por fonte termelétrica e exposições ao mercado de curto prazo que afetem os agentes de distribuição. Página 3 de 15 **==> picture [109 x 28] intentionally omitted <==** ##  ... |
| 10 | `proret-modulo06-subm6-8-proret-submod-6-8-v-1-4-aren2017760` | PRORET — Proret Submod 6.8 V 1.4 aren2017760 | Bandeira Tarifária Vermelha, segregada em Patamar 1 e 2. 8. A Bandeira Tarifária Verde indica condições favoráveis de geração de energia, não implicando acréscimo tarifário. 9. As  ... |

### Suas perguntas para inspecionar este caso

1. **H4 (dupla resposta):** os documentos que apareceram no top-10 (lista acima) também respondem a pergunta? Se sim, qual deles tem a resposta mais relevante?
2. **H6 (vocabulário):** se você reescrever a pergunta usando exatamente os termos do título/ementa do documento esperado, ela ainda soa natural? Que palavras-chave do documento esperado a pergunta atual NÃO usa?
3. **H11 (versão):** o documento esperado ainda está vigente em 2026? Foi revogado/substituído por outra norma? Se sim, qual?

---

## gt-0027

**Pergunta:** Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras?

**Resposta esperada (GT):** O Submódulo 2.4 estabelece metodologia para definição da taxa regulatória de remuneração de capital e da estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.

### Fonte esperada (ground truth)

**Fonte #1**
- `document_id`: `proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003`
- Título: PRORET — Proret Submod 2.4 V 4.1C aren20221003
- Citação: PRORET Submódulo 2.4, objetivo
- Section label: `Submódulo 2.4 - Custo de Capital`
- URL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.4/Proret_Submod_2.4_V_4.1C_aren20221003.pdf
- Support excerpt: > Estabelecer metodologia para definição da taxa regulatória de remuneração de capital e estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.
- Posição no retrieval: ****doc não aparece nem no top-100****

### Top-10 chunks devolvidos pela melhor config (o que o sistema achou que era relevante)

| rank | document_id | titulo | texto (preview) |
|---:|---|---|---|
| 1 | `proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091` | PRORET — Proret Submod 2.1 V 2.4 aren20241091 | ## **ANEXO XI** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição** **Submódulo 2.1** ## **PROCEDIMENTOS GERAIS** **Versão 2.4** ## **1. OBJETIVO 2. ABRAN ... |
| 2 | `proret-modulo02-subm2-1-proret-submod-2-1-v-2-3c-aren20221003` | PRORET — Proret Submod 2.1 V 2.3C aren20221003 | ## **ANEXO XI** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição Submódulo 2.1** ## **PROCEDIMENTOS GERAIS** **Versão 2.3 C** ## **1. OBJETIVO 2. ABRANGÊ ... |
| 3 | `proret-modulo2-subm2-1a-proret-submodulo-2-1a-v-2-2-anexo-xii` | PRORET — proret submodulo 2.1A V 2.2 Anexo XII | ## **ANEXO XII** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição** **Submódulo 2.1 A** ## **PROCEDIMENTOS GERAIS** **Aditivo Contratual 2016** **Versão  ... |
| 4 | `proret-modulo02-subm2-1a-proret-subm-2-1a-v-2-2-aren20251114` | PRORET — Proret subm 2.1A V 2.2 aren20251114 | ## **ANEXO XII** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição** **Submódulo 2.1 A** ## **PROCEDIMENTOS GERAIS** **Aditivo Contratual 2016** **Versão  ... |
| 5 | `proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-0c-aren20221003` | PRORET — Proret Submod 2.1A V 2.0C aren20221003 | ## **ANEXO XII** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição** **Submódulo 2.1 A** ## **PROCEDIMENTOS GERAIS** **Aditivo Contratual 2016** **Versão  ... |
| 6 | `proret-modulo2-subm2-1-proret-submodulo-2-1-v-2-5` | PRORET — proret submodulo 2.1 V 2.5 | ## **ANEXO XI** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição Submódulo 2.1** ## **PROCEDIMENTOS GERAIS** **Versão 2.5** ## **1. OBJETIVO 2. ABRANGÊNC ... |
| 7 | `proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114` | PRORET — Proret Submod 2.1 V 2.5 aren20251114 | ## **ANEXO XI** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição Submódulo 2.1** ## **PROCEDIMENTOS GERAIS** **Versão 2.5** ## **1. OBJETIVO 2. ABRANGÊNC ... |
| 8 | `proret-modulo02-subm2-1-proret-submod-2-1-v-2-3-aren2020874` | PRORET — Proret Submod 2.1 V 2.3 aren2020874 | . 7. Caso não haja tempo hábil para sua apuração, as informações do mercado faturado no último mês do período de referência serão estimadas, repetindo-se os montantes realizados no ... |
| 9 | `proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-1-aren20241091` | PRORET — Proret Submod 2.1A V 2.1 aren20241091 | ## **ANEXO XII** **Módulo 2: Revisão Tarifária Periódica das Concessionárias de Distribuição Submódulo 2.1 A** ## **PROCEDIMENTOS GERAIS** **Aditivo Contratual 2016** **Versão 2.0  ... |
| 10 | `proret-modulo02-subm2-1-proret-submod-2-1-v-2-1-aren2015686` | PRORET — Proret Submod 2.1 V 2.1 aren2015686 | referência serão estimadas, repetindo-se os montantes realizados no mês imediatamente anterior, podendo os valores do penúltimo mês, se provisórios, ser alterados, uma única vez, a ... |

### Suas perguntas para inspecionar este caso

1. **H4 (dupla resposta):** os documentos que apareceram no top-10 (lista acima) também respondem a pergunta? Se sim, qual deles tem a resposta mais relevante?
2. **H6 (vocabulário):** se você reescrever a pergunta usando exatamente os termos do título/ementa do documento esperado, ela ainda soa natural? Que palavras-chave do documento esperado a pergunta atual NÃO usa?
3. **H11 (versão):** o documento esperado ainda está vigente em 2026? Foi revogado/substituído por outra norma? Se sim, qual?
