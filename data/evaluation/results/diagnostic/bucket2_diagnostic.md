# 1.2b — Diagnóstico do balde 2 (gt-0005/17/25/34)

Após refutação de H8 em 1.2 (threshold 0.30 → 89% falsos positivos), o balde 2 voltou a ser falha real. Este documento explica caso a caso usando 6 categorias predefinidas.

Config: text-embedding-3-large + fixed-size + markdown + flat. Top-100 recuperados. Threshold de matching inalterado (0.60). Juiz: gpt-4o-mini.

## Resumo

| qid | doc rank top-100 | match rank | best cov top-10 | best cov geral | excerpt pos | juiz | **categoria** |
|---|---:|---:|---:|---:|---|---|---|
| gt-0005 | 1 | None | 0.5 | 1.0 | ausente | NAO | **fora_do_pool** |
| gt-0017 | 2 | None | 0.381 | 0.429 | ausente | NAO | **gt_ou_excerpt_problematico** |
| gt-0025 | 3 | None | 0.474 | 1.0 | single | NAO | **fora_do_pool** |
| gt-0034 | 1 | 14 | 0.5 | 1.0 | ausente | NAO | **fora_do_top10** |

---

## gt-0005

**Pergunta:** Em geração distribuída, quando uma usina fotovoltaica com armazenamento pode ser considerada central geradora de fonte despachável pela REN 1000/2021?

**Resposta esperada:** Quando a geração fotovoltaica de até 3 MW possuir capacidade de modulação via armazenamento de energia em baterias, em quantidade de pelo menos 20% da capacidade de geração mensal da central geradora.

**Doc esperado:** `ren-2021-1000` (261 chunks no índice)
**Section label:** `Art. 2º, definição de central geradora de fonte despachável`
**Support excerpt:** > central geradora de fonte despachável: ... geração fotovoltaica de até 3 MW de potência instalada, que apresentem capacidade de modulação de geração por meio do armazenamento de energia em baterias, em quantidade de, pelo menos, 20% da capacidade de geração mensal da central geradora.

**Métricas:**
- Primeiro chunk do doc em rank `1` (top-100)
- Primeiro chunk passando matching (threshold 0.60) em rank `None`
- Melhor cobertura no top-10: **0.5**
- Melhor cobertura considerando TODOS os chunks do doc: **1.0** (chunk index 1, rank no top-100: None)
- Position do excerpt: **ausente** (não bate como substring)

**Melhor chunk top-10** (rank 1, cov 0.500):
> fins de enquadramento de microgeração ou minigeração distribuída como central geradora de fonte despachável, o cálculo da produção média mensal da microgeração ou ## minigeração distribuída é obtido pela seguinte equação: (Incluído pela REN ANEEL 1.059, de 07.02.2023) 𝐸 = 𝑃 × 𝐹𝐶 × 24 ℎ𝑜𝑟𝑎𝑠 × 30 𝑑𝑖𝑎𝑠 𝑔 𝑔 em que: 𝐸𝑔 é a produção média mensal da microgeração ou minigeração distribuída; 𝑃𝑔 é a potênci

**Juiz LLM**: NAO — O chunk recuperado não menciona a capacidade de modulação via armazenamento de energia em baterias, que é a informação central necessária para considerar a usina fotovoltaica como central geradora de fonte despachável.

**Categoria atribuída: `fora_do_pool`**
Chunk com cobertura 1.00 (≥0.60) EXISTE no índice mas NÃO foi recuperado nem no top-100. Retrieval semântico não o priorizou.

---

## gt-0017

**Pergunta:** Em conexão de geração distribuída, qual requisito de anti-ilhamento deve ser observado segundo o PRODIST?

**Resposta esperada:** O sistema de anti-ilhamento deve garantir a desconexão física entre a rede de distribuição e as instalações elétricas internas da unidade consumidora com microgeração ou minigeração distribuída.

**Doc esperado:** `prodist-modulo-03` (50 chunks no índice)
**Section label:** `Módulo 3 - Conexão ao Sistema de Distribuição`
**Support excerpt:** > sistema de anti-ilhamento: sistema de controle responsável por garantir a desconexão física entre a rede de distribuição de energia elétrica e as instalações elétricas internas à unidade consumidora com microgeração ou minigeração distribuída.

**Métricas:**
- Primeiro chunk do doc em rank `2` (top-100)
- Primeiro chunk passando matching (threshold 0.60) em rank `None`
- Melhor cobertura no top-10: **0.381**
- Melhor cobertura considerando TODOS os chunks do doc: **0.429** (chunk index 8, rank no top-100: None)
- Position do excerpt: **ausente** (não bate como substring)

**Melhor chunk top-10** (rank 2, cov 0.381):
> Não é necessário relé de proteção específico, mas um sistema eletro-eletrônico que detecte tais anomalias e que produza uma saída capaz de operar na lógica de atuação do elemento de desconexão. - (4) Nas conexões acima de 300 kW, se o lado da acessada do transformador de acoplamento não for aterrado, deve-se usar uma proteção de sub e de sobretensão nos secundários de um conjunto de transformador 

**Juiz LLM**: NAO — O chunk recuperado não menciona o sistema de anti-ilhamento nem garante a desconexão física entre a rede de distribuição e as instalações elétricas internas, que é a informação central da resposta esperada.

**Categoria atribuída: `gt_ou_excerpt_problematico`**
Excerpt nem aparece como substring no doc (cov geral max=0.43), e o melhor chunk recuperado não sustenta a resposta. Provável paráfrase ou síntese conceitual.

---

## gt-0025

**Pergunta:** No PRORET Submódulo 2.3, quando imóveis sem título definitivo podem ser considerados na base de ativos?

**Resposta esperada:** Podem ser incluídos na base de remuneração se forem imóveis elegíveis ou operacionais, estiverem registrados na contabilidade, tiverem documentação que comprove a aquisição e houver comprovação de que a titularidade está em processo de regularização.

**Doc esperado:** `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003` (43 chunks no índice)
**Section label:** `Submódulo 2.3 - Ativos e imóveis`
**Support excerpt:** > Os imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária podem ser incluídos na base de remuneração, desde que se enquadrem nas seguintes condições: a) ser um imóvel elegível (imóvel operacional); b) encontrar-se registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) existir comprovação de que a documentação de titularidade de propriedade encontra-se em processo de regularização (protocolo em cartório ou similar).

**Métricas:**
- Primeiro chunk do doc em rank `3` (top-100)
- Primeiro chunk passando matching (threshold 0.60) em rank `None`
- Melhor cobertura no top-10: **0.474**
- Melhor cobertura considerando TODOS os chunks do doc: **1.0** (chunk index 3, rank no top-100: None)
- Position do excerpt: **single** (chunk index 3)

**Melhor chunk top-10** (rank 3, cov 0.474):
> valor aprovado na revisão tarifária anterior pela variação do IPCA. Nenhum valor deverá ser deduzido das Obrigações Especiais a título de baixas efetuadas na base blindada; d) deve ser levado em consideração o efeito da depreciação acumulada ocorrida entre as datas-bases da revisão tarifária anterior e a atual, obtendo-se o valor da base de remuneração blindada atualizada; e) os Índices de Aprovei

**Juiz LLM**: NAO — O chunk recuperado não contém informações sobre as condições específicas que permitem a inclusão de imóveis sem título definitivo na base de ativos, conforme descrito na resposta esperada.

**Categoria atribuída: `fora_do_pool`**
Chunk com cobertura 1.00 (≥0.60) EXISTE no índice mas NÃO foi recuperado nem no top-100. Retrieval semântico não o priorizou.

---

## gt-0034

**Pergunta:** O livre acesso ao sistema de transmissão assegurado no Módulo 5 equivale a acesso irrestrito ou a qualquer tempo?

**Resposta esperada:** Não. O Módulo 5 assegura livre acesso mediante pagamento dos encargos correspondentes e conforme condições gerais da ANEEL, mas afirma que livre acesso não se confunde com acesso irrestrito ou a qualquer tempo.

**Doc esperado:** `regtransm-modulo-05` (97 chunks no índice)
**Section label:** `Módulo 5 - Acesso ao Sistema`
**Support excerpt:** > É assegurado às centrais geradoras o livre acesso ao sistema de transmissão mediante pagamento dos encargos correspondentes ... não se confundindo o conceito de livre acesso com o conceito de acesso irrestrito ou a qualquer tempo.

**Métricas:**
- Primeiro chunk do doc em rank `1` (top-100)
- Primeiro chunk passando matching (threshold 0.60) em rank `14`
- Melhor cobertura no top-10: **0.5**
- Melhor cobertura considerando TODOS os chunks do doc: **1.0** (chunk index 1, rank no top-100: 14)
- Position do excerpt: **ausente** (não bate como substring)

**Melhor chunk top-10** (rank 5, cov 0.500):
> de 10 dias úteis e será identificado à parte dos EUST e destinado à modicidade da TUST-RB. 𝑃𝐼𝑈𝐺−𝑅𝐶 𝑚𝑎𝑥−𝑃(𝑖) −1,05 ⋅𝑀𝑈𝑆𝑇𝑃−𝑅𝐶(𝑖)) ⋅𝑇𝑈𝑆𝑇−𝑅𝐵𝑃(𝑖)] + 3 = 3 ⋅∑[(𝐷 𝑖 Eq. 6 𝑚𝑎𝑥−𝐹𝑃(𝑖) −1,05 ⋅𝑀𝑈𝑆𝑇𝐹𝑃−𝑅𝐶(𝑖)) ⋅𝑇𝑈𝑆𝑇−𝑅𝐵𝐹𝑃(𝑖)] ⋅∑[(𝐷 𝑖 Onde: 𝑃𝐼𝑈𝐺−𝑅𝐶 : parcela de ineficiência por ultrapassagem ao MUST contratado em caráter de reserva de capacidade a ser cobrada, em R$, quando seu valor for maior que zero; 𝐷𝑚𝑎𝑥−𝑃(𝑖) 

**Juiz LLM**: NAO — O chunk recuperado não contém informações sobre o livre acesso ao sistema de transmissão, nem menciona a distinção entre livre acesso e acesso irrestrito ou a qualquer tempo, que são essenciais para responder à pergunta.

**Categoria atribuída: `fora_do_top10`**
Chunk com cobertura 1.00 (≥0.60) existe em rank 14 (fora do top-10). Retrieval o encontrou, mas mal rankeado.

---

## Distribuição por categoria

| categoria | n |
|---|---:|
| `fora_do_pool` | 2 |
| `gt_ou_excerpt_problematico` | 1 |
| `fora_do_top10` | 1 |
