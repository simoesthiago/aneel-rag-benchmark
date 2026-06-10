# Auditoria das 24 falhas do RAG baseline — entrada para LLM externo

Cada caso traz: pergunta, ground truth (resposta esperada + documento + excerpt + URL oficial), resposta gerada, citações e métricas.

## gt-0002

**Pergunta:** Para fins da REN 1000/2021, o que são bandeiras tarifárias?

**Ground Truth:**

- resposta esperada: São um sistema aplicado por meio da tarifa de energia com a finalidade de sinalizar aos consumidores os custos atuais da geração de energia elétrica.
- documento: `ren-2021-1000` — Estabelece as Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica; revoga as Resoluções Normativas ANEEL nº 414, de 9 de setembro de 2010; nº 470, de 13 de dezembro de 2011; nº 901, de 8 de dezembro de 2020 e dá outras providências.
- seção: Art. 2º, definição de bandeiras tarifárias
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren20211000.pdf
- excerpt do trecho esperado:
  > bandeiras tarifárias: sistema que tem como finalidade sinalizar os custos atuais da geração de energia elétrica ao consumidor por meio da tarifa de energia.

**Resposta do sistema:**

- As bandeiras tarifárias são um sistema que sinaliza aos consumidores as condições de geração de energia elétrica no Sistema Interligado Nacional (SIN) e tem como finalidade a cobrança de um valor adicional à Tarifa de Energia (TE) em determinadas condições. Elas foram implementadas a partir de 2015 e se aplicam a todos os agentes de distribuição de energia elétrica, com exceção dos consumidores em Sistemas Isolados. O sistema é composto por três bandeiras: a Bandeira Tarifária Verde, que indica condições favoráveis de geração sem acréscimo tarifário; a Bandeira Tarifária Amarela, que indica condições menos favoráveis; e a Bandeira Tarifária Vermelha, que é dividida em Patamar 1 e Patamar 2, indicando condições críticas de geração que resultam em adicionais à TE [1][2][3][4]. A ANEEL é responsável por definir mensalmente qual bandeira será aplicada, com base em informações do Operador Nacional do Sistema (ONS) e da Câmara de Comercialização de Energia Elétrica (CCEE) [1][2][3].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 6.8 V 1.9C aren20221003, chunk 0
- PRORET — Proret Submod 6.8 V 1.10C aren20241084, chunk 0
- PRORET — Proret Submod 6.8 V 1.9 aren2020883, chunk 1
- PRORET — Proret Submod 6.8 V 1.9 aren2020883, chunk 0

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.92, faithfulness=0.98

---

## gt-0003

**Pergunta:** Como a REN 1000/2021 define consumidor?

**Ground Truth:**

- resposta esperada: Consumidor é a pessoa física ou jurídica que solicita o fornecimento do serviço à distribuidora, assumindo as obrigações decorrentes da prestação à sua unidade consumidora.
- documento: `ren-2021-1000` — Estabelece as Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica; revoga as Resoluções Normativas ANEEL nº 414, de 9 de setembro de 2010; nº 470, de 13 de dezembro de 2011; nº 901, de 8 de dezembro de 2020 e dá outras providências.
- seção: Art. 2º, definição de consumidor
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren20211000.pdf
- excerpt do trecho esperado:
  > consumidor: pessoa física ou jurídica que solicite o fornecimento do serviço à distribuidora, assumindo as obrigações decorrentes desta prestação à sua unidade consumidora.

**Resposta do sistema:**

- A REN 1000/2021 define consumidor como "pessoa física ou jurídica, de direito público ou privado, legalmente representada, que solicite o fornecimento, a contratação de energia ou o uso do sistema elétrico à distribuidora, assumindo as obrigações decorrentes deste atendimento à(s) sua(s) unidade(s) consumidora(s), segundo disposto nas normas e nos contratos" [7].

**Citações feitas pelo sistema:**
- Estabelece as Condições Gerais de Fornecimento de Energia Elétrica de forma atualizada e consolidada., chunk 2

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.72, faithfulness=0.98

---

## gt-0005

**Pergunta:** Em geração distribuída, quando uma usina fotovoltaica com armazenamento pode ser considerada central geradora de fonte despachável pela REN 1000/2021?

**Ground Truth:**

- resposta esperada: Quando a geração fotovoltaica de até 3 MW possuir capacidade de modulação via armazenamento de energia em baterias, em quantidade de pelo menos 20% da capacidade de geração mensal da central geradora.
- documento: `ren-2021-1000` — Estabelece as Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica; revoga as Resoluções Normativas ANEEL nº 414, de 9 de setembro de 2010; nº 470, de 13 de dezembro de 2011; nº 901, de 8 de dezembro de 2020 e dá outras providências.
- seção: Art. 2º, definição de central geradora de fonte despachável
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren20211000.pdf
- excerpt do trecho esperado:
  > central geradora de fonte despachável: ... geração fotovoltaica de até 3 MW de potência instalada, que apresentem capacidade de modulação de geração por meio do armazenamento de energia em baterias, em quantidade de, pelo menos, 20% da capacidade de geração mensal da central geradora.

**Resposta do sistema:**

- Uma usina fotovoltaica com armazenamento pode ser considerada uma central geradora de fonte despachável pela REN 1000/2021 se a sua potência instalada for de até 3 MW e se apresentar capacidade de modulação de geração por meio de armazenamento de energia em baterias, em quantidade de pelo menos 20% da capacidade de geração mensal das unidades de geração fotovoltaicas, conforme estabelecido no artigo 655-B [10].

**Citações feitas pelo sistema:**
- Aprimora as regras para a conexão e o faturamento de centrais de microgeração e minigeração distribuída em sistemas de distribuição de energia elétrica, bem como as regras do Sistema de Compensação de Energia Elétrica; altera as Resoluções Normativas n° 920, de 23 de fevereiro de 2021, 956, de 7 de dezembro de 2021, 1.000, de 7 de dezembro de 2021, 1009, de 22 de março de 2022, e dá outras providências., chunk 0

**Métricas:** failure_type=`retrieval_passage_failure`, recall=0.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.97, faithfulness=0.98

---

## gt-0007

**Pergunta:** Qual é o objeto regulatório central da REN 905/2020?

**Ground Truth:**

- resposta esperada: A REN 905/2020 aprova as Regras dos Serviços de Transmissão de Energia Elétrica no Sistema Elétrico Nacional.
- documento: `ren-2020-905` — Aprova as Regras dos Serviços de Transmissão de Energia Elétrica no Sistema Elétrico Nacional e dá outras providências.
- seção: Art. 1º
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren2020905.pdf
- excerpt do trecho esperado:
  > Ficam aprovadas as Regras dos Serviços de Transmissão de Energia Elétrica no Sistema Elétrico Nacional, na forma dos módulos anexos a esta Resolução.

**Resposta do sistema:**

- O objeto regulatório central da REN 905/2020 é a aprovação da versão do Submódulo 2.10 dos Procedimentos de Regulação Tarifária – PRORET, que dispõe sobre o ressarcimento ao consumidor dos custos acessórios da Conta-Covid por concessionária ou permissionária do serviço público de distribuição [1].

**Citações feitas pelo sistema:**
- Aprova a versão do Submódulo 2.10 dos Procedimentos de Regulação Tarifária – PRORET, dispõe sobre o ressarcimento ao consumidor dos custos acessórios da Conta-Covid por concessionária ou permissionária do serviço público de distribuição e altera as Resoluções Normativas nº 453, de 18 de outubro de 2011, e nº 791, de 14 de novembro de 2017., chunk 2

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.0, faithfulness=0.0

---

## gt-0012

**Pergunta:** Que elementos de formação de preço são consolidados pela REN 1032/2022?

**Ground Truth:**

- resposta esperada: A REN 1032/2022 consolida atos regulatórios relativos à elaboração do PMO e à formação do CMO e do PLD.
- documento: `ren-2022-1032` — Consolida os atos regulatórios relativos à elaboração do Programa Mensal da Operação Energética – PMO, e para a formação do Custo Marginal da Operação – CMO e do Preço de Liquidação de Diferenças – PLD; à atualização do valor do patamar da função de custo do déficit de energia elétrica; e aos critérios e procedimentos para o cálculo dos limites máximo e mínimo do Preço de Liquidação de Diferenças(PLD) e do valor da tarifa de energia de otimização referente à cessão de energia efetuada pelo comercializador de energia da Usina Hidroelétrica Itaipu (TEOItaipu).
- seção: Ementa
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren20221032.pdf
- excerpt do trecho esperado:
  > Consolida os atos regulatórios relativos à elaboração do Programa Mensal da Operação Energética – PMO, e para a formação do Custo Marginal da Operação – CMO e do Preço de Liquidação de Diferenças – PLD.

**Resposta do sistema:**

- Não há base suficiente no corpus para identificar os elementos de formação de preço consolidados pela REN 1032/2022.

**Citações feitas pelo sistema:**
- (nenhuma)

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.0, faithfulness=0.1

---

## gt-0013

**Pergunta:** Qual obrigação cadastral foi padronizada pela REN 1095/2024 para consumidores e demais usuários?

**Ground Truth:**

- resposta esperada: A REN 1095/2024 padroniza o número de identificação da unidade consumidora e das demais instalações dos usuários de energia elétrica.
- documento: `ren-2024-1095` — Estabelece a padronização do número de identificação da unidade consumidora e das demais instalações dos usuários de energia elétrica; altera as Resoluções Normativas nº 956, de 7 de dezembro de 2021, nº 1.000, de 7 de dezembro de 2021, e dá outras providências.
- seção: Ementa
- URL oficial ANEEL: https://www2.aneel.gov.br/cedoc/bren20241095.pdf
- excerpt do trecho esperado:
  > Estabelece a padronização do número de identificação da unidade consumidora e das demais instalações dos usuários de energia elétrica.

**Resposta do sistema:**

- A REN 1095/2024 padronizou a obrigação cadastral relacionada ao número de identificação da unidade consumidora e das demais instalações dos usuários de energia elétrica. Essa padronização estabelece que os cadastros, formulários, sistemas e outros instrumentos exigidos dos consumidores e demais usuários para a prestação de serviço público devem disponibilizar campo para registro do número de inscrição no CPF ou do CNPJ, de preenchimento ou informação obrigatórios, que será suficiente para sua identificação, vedada a exigência de apresentação de qualquer outro número para esse fim [4].

**Citações feitas pelo sistema:**
- Estabelece as Regras de Prestação do Serviço Público de Distribuição de Energia Elétrica; revoga as Resoluções Normativas ANEEL nº 414, de 9 de setembro de 2010; nº 470, de 13 de dezembro de 2011; nº 901, de 8 de dezembro de 2020 e dá outras providências., chunk 235

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.78, faithfulness=0.86

---

## gt-0015

**Pergunta:** Para interpretar termos usados nos módulos do PRODIST, qual é a finalidade da Seção 1.1 do Módulo 1?

**Ground Truth:**

- resposta esperada: A Seção 1.1 do Módulo 1 apresenta termos e expressões, com suas definições, relevantes para o entendimento dos módulos do PRODIST.
- documento: `prodist-modulo-01` — PRODIST — Módulo 1
- seção: Seção 1.1 - Glossário
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/master/procreg/prodist/modulo01/aren2008345_Prodist_modulo_1_v0.pdf
- excerpt do trecho esperado:
  > A seção 1.1 apresenta os termos e expressões, com as respectivas definições, relevantes para o entendimento dos módulos do PRODIST.

**Resposta do sistema:**

- A Seção 1.1 do Módulo 1 do PRODIST tem a finalidade de apresentar os fundamentos legais, as responsabilidades e as sanções relacionadas às atividades de distribuição de energia elétrica. Essa seção é essencial para entender a evolução institucional e a legislação setorial que se relaciona com o PRODIST, além de abordar as responsabilidades dos agentes e as sanções aplicáveis em caso de descumprimento das normas estabelecidas [3].

**Citações feitas pelo sistema:**
- PRODIST — Módulo 1, chunk 3

**Métricas:** failure_type=`answer_quality_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=1.0, correctness=0.18, faithfulness=0.86

---

## gt-0017

**Pergunta:** Em conexão de geração distribuída, qual requisito de anti-ilhamento deve ser observado segundo o PRODIST?

**Ground Truth:**

- resposta esperada: O sistema de anti-ilhamento deve garantir a desconexão física entre a rede de distribuição e as instalações elétricas internas da unidade consumidora com microgeração ou minigeração distribuída.
- documento: `prodist-modulo-03` — PRODIST — Módulo 3
- seção: Módulo 3 - Conexão ao Sistema de Distribuição
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/master/procreg/prodist/modulo03/aren2008345_Prodist_modulo_3_v0.pdf
- excerpt do trecho esperado:
  > sistema de anti-ilhamento: sistema de controle responsável por garantir a desconexão física entre a rede de distribuição de energia elétrica e as instalações elétricas internas à unidade consumidora com microgeração ou minigeração distribuída.

**Resposta do sistema:**

- O requisito de anti-ilhamento que deve ser observado segundo o PRODIST é que a proteção de anti-ilhamento deve garantir a desconexão física entre a rede de distribuição e as instalações elétricas internas à unidade consumidora, incluindo a parcela de carga e de geração, sendo vedada a conexão ao sistema da distribuidora durante a interrupção do fornecimento [1].

**Citações feitas pelo sistema:**
- Aprimora as regras para a conexão e o faturamento de centrais de microgeração e minigeração distribuída em sistemas de distribuição de energia elétrica, bem como as regras do Sistema de Compensação de Energia Elétrica; altera as Resoluções Normativas n° 920, de 23 de fevereiro de 2021, 956, de 7 de dezembro de 2021, 1.000, de 7 de dezembro de 2021, 1009, de 22 de março de 2022, e dá outras providências., chunk 28

**Métricas:** failure_type=`retrieval_passage_failure`, recall=0.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.92, faithfulness=0.98

---

## gt-0019

**Pergunta:** Na apuração de perdas regulatórias pelo PRODIST Módulo 7, quais perdas técnicas entram no cálculo sob responsabilidade da distribuidora?

**Ground Truth:**

- resposta esperada: Entram apenas as perdas técnicas sob responsabilidade da distribuidora, incluindo perdas no sistema de distribuição e, quando aplicável, em DIT; não entram perdas em instalações de terceiros.
- documento: `prodist-modulo-07` — PRODIST — Módulo 7
- seção: Módulo 7 - Cálculo de Perdas na Distribuição
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/master/procreg/prodist/modulo07/aren2008345_Prodist_modulo_7_v0.pdf
- excerpt do trecho esperado:
  > Somente as perdas técnicas de responsabilidade da distribuidora são consideradas, incluindo o sistema de distribuição e DIT, quando aplicável, não sendo consideradas as instalações de terceiros.

**Resposta do sistema:**

- As perdas técnicas que entram no cálculo sob responsabilidade da distribuidora incluem todas as perdas decorrentes da distribuição de energia elétrica, que são definidas como o montante de energia elétrica dissipada no sistema de distribuição em decorrência das leis da Física relativas aos processos de transporte, transformação de tensão e medição de energia elétrica. Essas perdas são apuradas e avaliadas conforme a metodologia estabelecida no Módulo 7 dos Procedimentos de Distribuição de Energia Elétrica no Sistema Elétrico Nacional – PRODIST, que considera as perdas técnicas de potência e de energia nos sistemas de distribuição [2][6][10].

**Citações feitas pelo sistema:**
- PRODIST — Módulo 7, chunk 0
- PRODIST — Módulo 7, chunk 1
- PRORET — Proret Submod 3.2A V 1.1C aren20221003, chunk 9

**Métricas:** failure_type=`citation_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.3333333333333333, correctness=0.84, faithfulness=0.78

---

## gt-0022

**Pergunta:** O que a BDGD representa no PRODIST Módulo 10?

**Ground Truth:**

- resposta esperada: A BDGD representa uma modelagem simplificada do sistema elétrico real para determinado período, refletindo ativos e informações técnicas e comerciais da distribuição.
- documento: `prodist-modulo-10` — PRODIST — Módulo 10
- seção: Módulo 10 - Sistema de Informação Geográfica Regulatório e BDGD
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/master/procreg/prodist/modulo10/aren2016730_Prodist_modulo_10_v0.pdf
- excerpt do trecho esperado:
  > O modelo BDGD é uma simplificação do sistema elétrico real para um determinado período, de forma a refletir os ativos e as informações técnicas e comerciais.

**Resposta do sistema:**

- A BDGD, ou Base de Dados Geográfica da Distribuidora, representa o conjunto de informações que são encaminhadas pela distribuidora e que compõem o Sistema de Informação Geográfica Regulatório (SIG-R). Ela é fundamental para a regulação e fiscalização da ANEEL, pois contém dados técnicos do sistema de distribuição, informações comerciais e dados físico-contábeis da base de ativos [6][9]. A BDGD é organizada em entidades geográficas e não geográficas, e deve ser enviada em conformidade com as especificações e prazos estabelecidos no PRODIST [1][4].

**Citações feitas pelo sistema:**
- PRODIST — Módulo 10, chunk 8
- PRODIST — Módulo 10, chunk 2
- PRODIST — Módulo 10, chunk 1
- PRODIST — Módulo 10, chunk 0

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.25, correctness=0.78, faithfulness=0.92

---

## gt-0023

**Pergunta:** No PRORET Submódulo 2.1, como é calculado o Valor da Parcela A?

**Ground Truth:**

- resposta esperada: O Valor da Parcela A é calculado pela soma VPA = CE + CT + ES, em que CE é custo de aquisição de energia e geração própria, CT é custo de conexão e uso dos sistemas de transmissão/distribuição, e ES são encargos setoriais.
- documento: `proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114` — PRORET — Proret Submod 2.1 V 2.5 aren20251114
- seção: Submódulo 2.1 - Parcela A
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.1/Proret_Submod_2.1_V_2.5_aren20251114.pdf
- excerpt do trecho esperado:
  > A Parcela A é composta pela soma dos componentes abaixo: VPA=CE+CT+ES; CE: Custo de aquisição de energia elétrica e geração própria; CT: Custo com conexão e uso dos sistemas; ES: Encargos setoriais.

**Resposta do sistema:**

- O Valor da Parcela A (VPA) é calculado pela soma dos seguintes componentes: Custo de aquisição de energia elétrica e geração própria (CE), Custo com conexão e uso dos sistemas de transmissão e/ou distribuição (CT), Encargos setoriais definidos em legislação específica (ES) e Receitas Irrecuperáveis (RI). A fórmula é: VPA = CE + CT + ES + RI [1]. Os procedimentos de cálculo detalhados de cada um dos componentes estão descritos nos Submódulos 2.2A, 3.2A, 3.3A e 3.4A do PRORET [10].

**Citações feitas pelo sistema:**
- PRORET — proret submodulo 2.1 V 2.5, chunk 1
- PRORET — Proret Submod 2.1A V 2.1 aren20241091, chunk 1

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.08, faithfulness=0.12

---

## gt-0024

**Pergunta:** Quais componentes de custo compõem a Parcela A no PRORET Submódulo 2.1?

**Ground Truth:**

- resposta esperada: A Parcela A é composta por custo de aquisição de energia elétrica e geração própria, custo com conexão e uso dos sistemas de transmissão e/ou distribuição, e encargos setoriais definidos em legislação específica.
- documento: `proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114` — PRORET — Proret Submod 2.1 V 2.5 aren20251114
- seção: Submódulo 2.1 - Parcela A
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.1/Proret_Submod_2.1_V_2.5_aren20251114.pdf
- excerpt do trecho esperado:
  > CE: Custo de aquisição de energia elétrica e geração própria; CT: Custo com conexão e uso dos sistemas de transmissão e/ou distribuição; e ES: Encargos setoriais definidos em legislação específica.

**Resposta do sistema:**

- A Parcela A é composta pela soma dos seguintes componentes: CE (Custo de aquisição de energia elétrica e geração própria), CT (Custo com conexão e uso dos sistemas de transmissão e/ou distribuição), ES (Encargos setoriais definidos em legislação específica) e RI (Receitas Irrecuperáveis) [6]. Portanto, a equação que representa a Parcela A é VPA = CE + CT + ES + RI [9].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 2.1A V 2.1 aren20241091, chunk 1
- PRORET — proret submodulo 2.1A V 2.2 Anexo XII, chunk 1

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.72, faithfulness=0.98

---

## gt-0025

**Pergunta:** No PRORET Submódulo 2.3, quando imóveis sem título definitivo podem ser considerados na base de ativos?

**Ground Truth:**

- resposta esperada: Podem ser incluídos na base de remuneração se forem imóveis elegíveis ou operacionais, estiverem registrados na contabilidade, tiverem documentação que comprove a aquisição e houver comprovação de que a titularidade está em processo de regularização.
- documento: `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003` — PRORET — Proret Submod 2.3 V 2.0C aren20221003
- seção: Submódulo 2.3 - Ativos e imóveis
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.3/Proret_Submod_2.3_V_2.0C_aren20221003.pdf
- excerpt do trecho esperado:
  > Os imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária podem ser incluídos na base de remuneração, desde que se enquadrem nas seguintes condições: a) ser um imóvel elegível (imóvel operacional); b) encontrar-se registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) existir comprovação de que a documentação de titularidade de propriedade encontra-se em processo de regularização (protocolo em cartório ou similar).

**Resposta do sistema:**

- Os imóveis que não possuem documentação de titularidade de propriedade definitiva em nome da transmissora podem ser considerados na base de ativos, desde que atendam aos seguintes critérios: a) ser um imóvel elegível (imóvel operacional); b) estar registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) apresentar documentação que comprove que a titularidade de propriedade se encontra em processo de regularização (protocolo em cartório ou similar) [2][4].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 2.3 V 2.0 aren2015686, chunk 5
- PRORET — Proret Submod 2.3 V 1.1 aren2013544, chunk 32

**Métricas:** failure_type=`retrieval_passage_failure`, recall=0.0, doc_recall=1.0, citation_accuracy=0.0, correctness=1.0, faithfulness=1.0

---

## gt-0026

**Pergunta:** Que parâmetros estatísticos o PRORET Submódulo 2.3 usa para cálculo de tamanho de amostra?

**Ground Truth:**

- resposta esperada: O tamanho da amostra é calculado pela ANEEL com intervalo de confiança de 95%, Z igual a 1,96, margem de erro de 10% e proporção de 75%.
- documento: `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003` — PRORET — Proret Submod 2.3 V 2.0C aren20221003
- seção: Submódulo 2.3 - Cálculo amostral
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.3/Proret_Submod_2.3_V_2.0C_aren20221003.pdf
- excerpt do trecho esperado:
  > O tamanho da amostra é calculado pela ANEEL utilizando intervalo de confiança de 95% (Z=1,96), margem de erro de 10% e proporção de 75%.

**Resposta do sistema:**

- O PRORET Submódulo 2.3 utiliza a seguinte metodologia para o cálculo do tamanho da amostra: considera um intervalo de confiança de 95% (Z igual a 1,96), uma margem de erro amostral de 10% (e) e uma estimativa inicial da proporção das "linhas e redes" com uma determinada característica esperada na concessionária (P0) de 75%. A fórmula utilizada é: m = 2 / (e * (M - 1)) + 1 / (2 * Z * [P0 * (1 - P0)]) onde m é o tamanho da amostra, M é a quantidade total de conjuntos da concessionária, e é a margem de erro amostral, Z é o intervalo de confiança e P0 é a característica esperada [8][9].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 2.3 V 2.0 aren2015686, chunk 26
- Altera o submódulo 2.3 dos Procedimentos de Regulação Tarifária – PRORET., chunk 22

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.88, faithfulness=0.92

---

## gt-0027

**Pergunta:** Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras?

**Ground Truth:**

- resposta esperada: O Submódulo 2.4 estabelece metodologia para definição da taxa regulatória de remuneração de capital e da estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.
- documento: `proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003` — PRORET — Proret Submod 2.4 V 4.1C aren20221003
- seção: Submódulo 2.4 - Custo de Capital
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo02/subm2.4/Proret_Submod_2.4_V_4.1C_aren20221003.pdf
- excerpt do trecho esperado:
  > Estabelecer metodologia para definição da taxa regulatória de remuneração de capital e estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.

**Resposta do sistema:**

- A finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras é estabelecer os procedimentos gerais para o cálculo da Receita Requerida (RR) nas Revisões Tarifárias Periódicas das concessionárias de serviço público de distribuição de energia elétrica. O reposicionamento das tarifas compreende duas etapas: o cálculo da Receita Requerida e a abertura tarifária, que é realizada após a definição da RR e do Mercado de Referência [1].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 2.1 V 2.4 aren20241091, chunk 0

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.03, faithfulness=0.12

---

## gt-0028

**Pergunta:** Para que servem as Tarifas de Referência calculadas no PRORET Submódulo 7.2?

**Ground Truth:**

- resposta esperada: As Tarifas de Referência são necessárias para a definição da Tarifa de Uso do Sistema de Distribuição (TUSD) e da Tarifa de Energia (TE).
- documento: `proret-modulo07-subm7-2-proret-submod-7-2-v-2-5-aren20231060` — PRORET — Proret Submod 7.2 V 2.5 aren20231060
- seção: Submódulo 7.2 - Tarifas de Referência
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo07/subm7.2/Proret_Submod_7.2_V_2.5_aren20231060.pdf
- excerpt do trecho esperado:
  > Estabelecer a metodologia de cálculo das Tarifas de Referência, necessárias para a definição da Tarifa de Uso do Sistema de Distribuição – TUSD e da Tarifa de Energia – TE.

**Resposta do sistema:**

- As Tarifas de Referência calculadas no PRORET Submódulo 7.2 servem para determinar a relatividade de tarifas entre as diversas modalidades e subgrupos tarifários, sendo fundamentais para o cálculo da TUSD e TE de Aplicação, que são compostas pela base econômica e pelos componentes tarifários financeiros [5]. Além disso, as Tarifas de Referência são utilizadas para apurar a receita de referência, que é o produto das tarifas de referência pelo mercado de referência [2].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 8.3 V 2.2 aren20231058, chunk 2
- PRORET — Proret Submod 8.3 V 2.1 aren2017773, chunk 1

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.72, faithfulness=0.98

---

## gt-0029

**Pergunta:** Que obrigação informacional é definida no PRORET Submódulo 10.6?

**Ground Truth:**

- resposta esperada: O Submódulo 10.6 define a forma e a periodicidade das informações que distribuidoras, CCEE e ONS devem encaminhar à ANEEL no âmbito da distribuição de energia elétrica.
- documento: `proret-modulo10-subm10-6-proret-submod-10-6-v-1-2-aren2024109` — PRORET — Proret Submod 10.6 V 1.2 aren2024109
- seção: Submódulo 10.6 - Informações periódicas da distribuição
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/proret/modulo10/subm10.6/Proret_Submod_10.6_V_1.2_aren2024109.pdf
- excerpt do trecho esperado:
  > Definir a forma e periodicidade das informações a serem encaminhadas à ANEEL, no âmbito da distribuição de energia elétrica, pelas distribuidoras, pela CCEE e pelo ONS.

**Resposta do sistema:**

- A obrigação informacional definida no PRORET Submódulo 10.6 é a de que as distribuidoras de energia elétrica, a Câmara de Comercialização de Energia Elétrica (CCEE) e o Operador Nacional do Sistema Elétrico (ONS) devem encaminhar informações periódicas à ANEEL. Essas informações devem ser enviadas mensalmente e incluem dados sobre a classificação, demanda, energia, microgeração, subsídios, receitas, tributos e reativos, entre outros, conforme especificado nas tabelas do submódulo [1][3][10].

**Citações feitas pelo sistema:**
- PRORET — Proret Submod 10.6 V 1.0 aren2018812, chunk 0
- PRORET — Proret Submod 10.6 V 1.1 aren2018819, chunk 0
- PRORET — Proret Submod 10.6 V 1.1 aren2018819, chunk 1

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.95, faithfulness=0.98

---

## gt-0030

**Pergunta:** Como o Módulo 1 das Regras de Transmissão define a Duração Equivalente da Indisponibilidade na FT-Conversora?

**Ground Truth:**

- resposta esperada: É a ponderação da duração real da indisponibilidade na FT-Conversora pela redução da capacidade de transmissão de potência decorrente dessa indisponibilidade.
- documento: `regtransm-modulo-01` — Regras de Transmissão — Módulo 1 — Glossário
- seção: Glossário - Duração Equivalente da Indisponibilidade na FT-Conversora
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/regtransm/Modulo 01_Glossario_aren2020905_2.pdf
- excerpt do trecho esperado:
  > Duração Equivalente da Indisponibilidade na FT-Conversora: ponderação da Duração Real da Indisponibilidade na FT-Conversora pela redução da capacidade de transmissão de potência decorrente da Indisponibilidade na FT-Conversora.

**Resposta do sistema:**

- O Módulo 1 das Regras de Transmissão define a Duração Equivalente da Indisponibilidade na FT-Conversora como um cálculo que considera o número de alterações na capacidade de transmissão de potência durante a indisponibilidade, o período da indisponibilidade em minutos e a capacidade de transmissão de potência reduzida. A fórmula para o cálculo é: DEI = (Σ (dj * Pj)) / Pnom, onde DEI é a Duração Equivalente da Indisponibilidade, N é o número de alterações, dj é o período da indisponibilidade em minutos e Pj é a capacidade reduzida durante esse período, enquanto Pnom é a capacidade nominal contratada de transmissão de potência [1][4].

**Citações feitas pelo sistema:**
- Regras de Transmissão — Módulo 4 — Prestação dos Serviços, chunk 27
- Regras de Transmissão — Módulo 4 — Prestação dos Serviços, chunk 28

**Métricas:** failure_type=`retrieval_document_failure`, recall=0.0, doc_recall=0.0, citation_accuracy=0.0, correctness=0.12, faithfulness=0.18

---

## gt-0034

**Pergunta:** O livre acesso ao sistema de transmissão assegurado no Módulo 5 equivale a acesso irrestrito ou a qualquer tempo?

**Ground Truth:**

- resposta esperada: Não. O Módulo 5 assegura livre acesso mediante pagamento dos encargos correspondentes e conforme condições gerais da ANEEL, mas afirma que livre acesso não se confunde com acesso irrestrito ou a qualquer tempo.
- documento: `regtransm-modulo-05` — Regras de Transmissão — Módulo 5 — Acesso ao Sistema
- seção: Módulo 5 - Acesso ao Sistema
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/procreg/regtransm/Modulo 05_Acesso_Sistema_aren2020905_2_4.pdf
- excerpt do trecho esperado:
  > É assegurado às centrais geradoras o livre acesso ao sistema de transmissão mediante pagamento dos encargos correspondentes ... não se confundindo o conceito de livre acesso com o conceito de acesso irrestrito ou a qualquer tempo.

**Resposta do sistema:**

- O livre acesso ao sistema de transmissão assegurado no Módulo 5 não equivale a acesso irrestrito ou a qualquer tempo. O conceito de livre acesso é distinto desses termos, conforme mencionado na regulamentação [2].

**Citações feitas pelo sistema:**
- Procedimentos de Rede — Acesso às instalações de transmissão, chunk 8

**Métricas:** failure_type=`retrieval_passage_failure`, recall=0.0, doc_recall=1.0, citation_accuracy=0.0, correctness=0.96, faithfulness=0.98

---

## gt-0037

**Pergunta:** Além da conexão às instalações de transmissão, que conexão de geração também é coberta pelo Submódulo 2.10-RQ dos Procedimentos de Rede?

**Ground Truth:**

- resposta esperada: O Submódulo 2.10-RQ também apresenta requisitos técnicos mínimos com impacto sistêmico para conexão de centrais de geração às instalações sob responsabilidade de distribuidora em tensão superior a 69 kV.
- documento: `proc-rede-2-10-rq` — Procedimentos de Rede — Requisitos técnicos mínimos para a conexão às instalações de transmissão
- seção: Submódulo 2.10-RQ - Objetivo
- URL oficial ANEEL: https://proxyportais.ons.org.br/ons.portalempregado.proxy/garapi/api/processo/retornarpdf?url=/sites/soumaisons/portalgar/ecmpdf/Subm%C3%B3dulo%202.10-RQ_2025.02.pdf
- excerpt do trecho esperado:
  > Este submódulo também tem como objetivo apresentar os requisitos técnicos mínimos com impacto sistêmico para a conexão de centrais de geração às instalações sob responsabilidade de distribuidora em nível de tensão superior a 69 kV.

**Resposta do sistema:**

- Além da conexão às instalações de transmissão, o Submódulo 2.10-RQ dos Procedimentos de Rede também cobre a conexão de centrais geradoras, incluindo usinas hidroelétricas, termoelétricas, e centrais geradoras eólicas e fotovoltaicas, conforme os requisitos técnicos mínimos estabelecidos para essas instalações [1][2][5].

**Citações feitas pelo sistema:**
- Procedimentos de Rede — Requisitos técnicos mínimos para a conexão às instalações de transmissão, chunk 4
- Procedimentos de Rede — Requisitos técnicos mínimos para a conexão às instalações de transmissão, chunk 1
- Procedimentos de Rede — Requisitos técnicos mínimos para a conexão às instalações de transmissão, chunk 20

**Métricas:** failure_type=`citation_and_answer_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.3333333333333333, correctness=0.18, faithfulness=0.92

---

## gt-0039

**Pergunta:** Quais elementos do Sistema de Medição para Faturamento são abrangidos pelo Submódulo 2.14-RQ?

**Ground Truth:**

- resposta esperada: O submódulo estabelece requisitos para o SMF, incluindo comunicação de dados, recursos de programação, medição de retaguarda, localização dos pontos de medição e arquitetura básica do sistema.
- documento: `proc-rede-2-14-rq` — Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento
- seção: Submódulo 2.14-RQ - Objetivo
- URL oficial ANEEL: https://proxyportais.ons.org.br/ons.portalempregado.proxy/garapi/api/processo/retornarpdf?url=/sites/soumaisons/portalgar/ecmpdf/Subm%C3%B3dulo%202.14-RQ_2022.11.pdf
- excerpt do trecho esperado:
  > Estabelecer os requisitos para o Sistema de Medição para Faturamento (SMF), inclusive para a comunicação de dados, recursos de programação, medição de retaguarda, localização dos pontos de medição e arquitetura básica do SMF.

**Resposta do sistema:**

- Os elementos do Sistema de Medição para Faturamento abrangidos pelo Submódulo 2.14-RQ incluem: requisitos gerais para o sistema, medidores (incluindo características elétricas, classe de exatidão, certificado, grandezas a medir, memória de massa, relógio/calendário interno, preservação dos registros, leitura dos registros, autodiagnose, e qualidade de energia elétrica), transformadores para instrumentos, cabeamento secundário, comunicação de dados, recursos de programação, medição de retaguarda, e localização dos pontos de medição [1][2][3][5][6].

**Citações feitas pelo sistema:**
- Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento, chunk 0
- Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento, chunk 1
- Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento, chunk 2
- Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento, chunk 6
- Procedimentos de Rede — Requisitos mínimos para o Sistema de Medição para Faturamento, chunk 4

**Métricas:** failure_type=`citation_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.4, correctness=0.95, faithfulness=0.98

---

## gt-0041

**Pergunta:** Na apuração mensal do Submódulo 8.3-PR, quais parcelas são consideradas no VMEuRB?

**Ground Truth:**

- resposta esperada: São considerados os EUST relativos à Rede Básica em função do MUST contratado e da TUSTRB, os EUST de importação ou exportação de energia elétrica e eventuais diferenças entre MUST verificado e MUST contratado.
- documento: `proc-rede-8-3-pr` — Procedimentos de Rede — Apuração mensal de serviços e encargos da transmissão e encargos setoriais
- seção: Submódulo 8.3-PR - Apuração de encargos
- URL oficial ANEEL: https://proxyportais.ons.org.br/ons.portalempregado.proxy/garapi/api/processo/retornarpdf?url=/sites/soumaisons/portalgar/ecmpdf/Subm%C3%B3dulo%208.3-PR_2025.06.pdf
- excerpt do trecho esperado:
  > Para a apuração do VMEuRB são considerados: EUST relativos à Rede Básica em função do MUST contratado e da TUSTRB; EUST relativos à importação ou exportação de energia elétrica; e eventuais diferenças de encargos entre MUST verificado e MUST contratado.

**Resposta do sistema:**

- Na apuração do VMEuRB, são consideradas as seguintes parcelas: (a) Encargos de Uso do Sistema de Transmissão (EUST) relativos à Rede Básica em função do MUST contratado e da TUSTRB; (b) EUST relativos à importação ou exportação de energia elétrica em função da TUSTIMP/EXP e quando uso de Interligações Internacionais também em função da TUII; (c) eventuais diferenças de encargos, configuradas entre MUST verificado e MUST contratado, apuradas no mês anterior; (d) encargo relativo à TUSDg-T a ser atribuído à concessionária ou permissionária de distribuição que tenha CUST celebrado com o ONS; (e) encargo relativo à TUSDg-ONS a ser atribuído à distribuidora que tenha CUST celebrado com o ONS; (f) encargo relativo ao repasse de potência oriunda da Itaipu Binacional; (g) encargo relativo ao ressarcimento financeiro às agentes de transmissão em caso de sobrecarga de transformadores; (h) montante financeiro relativo à Parcela de Ineficiência por Ultrapassagem (PIU) do MUST contratado; (i) montante financeiro relativo à Parcela de Ineficiência por Sobrecontratação (PIS) do MUST contratado; (j) montante financeiro de retificação de encargos apurados nos meses anteriores; e (k) encargo de reserva da rede de transmissão associado ao período de postergação da data de início de execução do CUST [2].

**Citações feitas pelo sistema:**
- Procedimentos de Rede — Apuração mensal de serviços e encargos da transmissão e encargos setoriais, chunk 2

**Métricas:** failure_type=`answer_quality_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=1.0, correctness=0.22, faithfulness=0.98

---

## gt-0046

**Pergunta:** Depois da publicação do POTEE, o que a SCT faz na rotina de autorização de reforços sem receita prévia?

**Ground Truth:**

- resposta esperada: A SCT analisa os reforços indicados no POTEE para determinar a autorização de implantação; o despacho indica a concessionária responsável, escopo, prazo de execução, data de necessidade e indicação no SGPMR.
- documento: `manual-transmissao-rotina-operacional-padrao-para-autorizacao-de-reforcos-sem-receita-previa` — Rotina Operacional Padrão para autorização de reforços sem receita prévia
- seção: Procedimentos - análise SCT
- URL oficial ANEEL: https://git.aneel.gov.br/publico/centralconteudo/-/raw/main/manuaisminstrucoes/transmissao/2021_Rotina_op_padrao_autoriza_reforcos_sem_receita_previa.pdf
- excerpt do trecho esperado:
  > Publicado o POTEE, a SCT analisa os reforços indicados neste documento para determinar a autorização para sua implantação. O Despacho da SCT indicará a concessionária responsável, o escopo do reforço, o prazo para execução, a data de necessidade e sua indicação no SGPMR.

**Resposta do sistema:**

- Após a publicação do POTEE, a SCT analisa os reforços indicados neste documento para determinar a autorização para sua implantação. O despacho da SCT indicará a concessionária responsável pela implantação do reforço, o escopo do reforço, o prazo para execução, a data de necessidade, bem como sua indicação no SGPMR - Sistema de Gerenciamento dos Planos de Melhorias e Reforços [2]. A SCT também avalia a razoabilidade dos prazos indicados no POTEE em face da natureza da obra e dos prazos médios de implementação apresentados na Nota Técnica n° 835/2018-SCT/ANEEL [3]. Além disso, as transmissoras podem solicitar para a ANEEL o estabelecimento de RAP para ANEEL no subsequente processo de reajuste anual de receitas das transmissoras após a entrada em operação comercial desses reforços [4].

**Citações feitas pelo sistema:**
- Rotina Operacional Padrão para autorização de reforços sem receita prévia, chunk 0
- Rotina Operacional Padrão para autorização de reforços sem receita prévia, chunk 2
- Rotina Operacional Padrão para autorização de reforços sem receita prévia, chunk 1

**Métricas:** failure_type=`citation_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=0.3333333333333333, correctness=0.86, faithfulness=0.98

---

## gt-0049

**Pergunta:** Nos serviços de energia elétrica, como a Lei 9.074/1995 enquadra concessões, permissões e autorizações?

**Ground Truth:**

- resposta esperada: A lei determina que concessões, permissões e autorizações para exploração de serviços e instalações de energia elétrica e aproveitamento energético de cursos d’água sejam contratadas, prorrogadas ou outorgadas nos termos da própria Lei 9.074/1995, da Lei 8.987/1995 e das demais normas aplicáveis.
- documento: `lei-9074-1995` — Lei 9.074/1995 — Outorgas e Prorrogações de Concessões
- seção: Art. 4º
- URL oficial ANEEL: https://www.planalto.gov.br/ccivil_03/leis/l9074compilada.htm
- excerpt do trecho esperado:
  > As concessões, permissões e autorizações de exploração de serviços e instalações de energia elétrica e de aproveitamento energético dos cursos de água serão contratadas, prorrogadas ou outorgadas nos termos desta e da Lei nº 8.987, e das demais.

**Resposta do sistema:**

- A Lei 9.074/1995 regula as concessões, permissões e autorizações para a exploração de serviços e instalações de energia elétrica, estabelecendo que essas outorgas devem ser contratadas, prorrogadas ou outorgadas conforme os termos da própria lei e da Lei nº 8.987/1995. As concessões de geração de energia elétrica têm um prazo de até 35 anos, podendo ser prorrogadas por até 20 anos, enquanto as concessões de transmissão e distribuição têm um prazo de até 30 anos, também passível de prorrogação. Além disso, a lei determina que as outorgas podem ser feitas a título oneroso em favor da União [1].

**Citações feitas pelo sistema:**
- Lei 9.074/1995 — Outorgas e Prorrogações de Concessões, chunk 1

**Métricas:** failure_type=`answer_quality_failure`, recall=1.0, doc_recall=1.0, citation_accuracy=1.0, correctness=0.72, faithfulness=0.98

---
