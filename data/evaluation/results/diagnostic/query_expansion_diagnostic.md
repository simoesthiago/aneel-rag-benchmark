# 1.3-alt — Query expansion contra gap de vocabulário (H6)

Teste de 3 variantes de query (ORIGINAL, GENERIC_EXPANSION, ORACLE_EXPANSION) nas 3 perguntas com gap formal-vs-informal (gt-0005, gt-0025, gt-0027).

Config: text-embedding-3-large + fixed-size + markdown + flat. Top-100 recuperados; passage_recall e doc_recall medidos em top-10. Matching threshold inalterado (0.6).

**Reescrita por:** gpt-4o-mini (temperatura 0).

**Importante:** ORACLE_EXPANSION usa termos do documento esperado — é DIAGNÓSTICO (ceiling), não proposta de produto. Apenas GENERIC_EXPANSION é realístico para produção.


## Resumo agregado

| qid | variante | passage_recall@10 | doc_recall@10 | primeiro chunk doc | primeiro match | chunk perfeito (rank/cov) |
|---|---|---:|---:|---:|---:|---|
| gt-0005 | ORIGINAL | 0.0 | 1.0 | 1 | None | fora pool / cov 1.0 |
| gt-0005 | GENERIC_EXPANSION | 0.0 | 1.0 | 6 | None | fora pool / cov 1.0 |
| gt-0005 | ORACLE_EXPANSION | 0.0 | 1.0 | 1 | None | fora pool / cov 1.0 |
| gt-0025 | ORIGINAL | 0.0 | 1.0 | 3 | None | fora pool / cov 1.0 |
| gt-0025 | GENERIC_EXPANSION | 0.0 | 1.0 | 4 | None | fora pool / cov 1.0 |
| gt-0025 | ORACLE_EXPANSION | 0.0 | 0.0 | 14 | 41 | rank 41 / cov 1.0 |
| gt-0027 | ORIGINAL | 0.0 | 0.0 | None | None | fora pool / cov 1.0 |
| gt-0027 | GENERIC_EXPANSION | 0.0 | 0.0 | None | None | fora pool / cov 1.0 |
| gt-0027 | ORACLE_EXPANSION | 0.0 | 0.0 | None | None | fora pool / cov 1.0 |

---

## gt-0005

**Doc esperado:** `ren-2021-1000`

**Support excerpt:** > central geradora de fonte despachável: ... geração fotovoltaica de até 3 MW de potência instalada, que apresentem capacidade de modulação de geração por meio do armazenamento de energia em baterias, em quantidade de, pelo menos, 20% da capacidade de geração mensal da central geradora.


### ORIGINAL

**Query:** Em geração distribuída, quando uma usina fotovoltaica com armazenamento pode ser considerada central geradora de fonte despachável pela REN 1000/2021?

- passage_recall@10 = **0.0**
- doc_recall@10 = **1.0**
- primeiro chunk do doc no top-100: rank `1`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### GENERIC_EXPANSION

**Query:** Em conformidade com a Resolução Normativa nº 1000/2021, em que circunstâncias uma usina fotovoltaica com sistema de armazenamento pode ser classificada como central geradora de fonte despachável no contexto da geração distribuída?

- passage_recall@10 = **0.0**
- doc_recall@10 = **1.0**
- primeiro chunk do doc no top-100: rank `6`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### ORACLE_EXPANSION

**Query:** Em geração distribuída, quando uma usina fotovoltaica com armazenamento pode ser considerada central geradora de fonte despachável, considerando a geração fotovoltaica de até 3 MW de potência instalada e a capacidade de modulação de geração por meio do armazenamento de energia em baterias, em quantidade de, pelo menos, 20% da capacidade de geração mensal da central geradora, conforme a REN 1000/2021?

- passage_recall@10 = **0.0**
- doc_recall@10 = **1.0**
- primeiro chunk do doc no top-100: rank `1`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

---

## gt-0025

**Doc esperado:** `proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003`

**Support excerpt:** > Os imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária podem ser incluídos na base de remuneração, desde que se enquadrem nas seguintes condições: a) ser um imóvel elegível (imóvel operacional); b) encontrar-se registrado na contabilidade; c) existir documentação que comprove a aquisição; e d) existir comprovação de que a documentação de titularidade de propriedade encontra-se em processo de regularização (protocolo em cartório ou similar).


### ORIGINAL

**Query:** No PRORET Submódulo 2.3, quando imóveis sem título definitivo podem ser considerados na base de ativos?

- passage_recall@10 = **0.0**
- doc_recall@10 = **1.0**
- primeiro chunk do doc no top-100: rank `3`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### GENERIC_EXPANSION

**Query:** No âmbito do PRORET, especificamente no Submódulo 2.3, em quais condições imóveis desprovidos de título definitivo podem ser incluídos na base de ativos regulatórios?

- passage_recall@10 = **0.0**
- doc_recall@10 = **1.0**
- primeiro chunk do doc no top-100: rank `4`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### ORACLE_EXPANSION

**Query:** No PRORET Submódulo 2.3, quais são as condições para que imóveis que não possuam documentação de titularidade de propriedade definitiva em nome da concessionária possam ser incluídos na base de remuneração?

- passage_recall@10 = **0.0**
- doc_recall@10 = **0.0**
- primeiro chunk do doc no top-100: rank `14`
- primeiro chunk passando matching: rank `41`
- chunk perfeito (cov 1.0): rank `41` no top-100

---

## gt-0027

**Doc esperado:** `proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003`

**Support excerpt:** > Estabelecer metodologia para definição da taxa regulatória de remuneração de capital e estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.


### ORIGINAL

**Query:** Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras?

- passage_recall@10 = **0.0**
- doc_recall@10 = **0.0**
- primeiro chunk do doc no top-100: rank `None`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### GENERIC_EXPANSION

**Query:** Qual é a finalidade da metodologia regulatória estabelecida no Submódulo 2.4 do PRORET no contexto da revisão tarifária periódica das concessionárias de distribuição de energia elétrica?

- passage_recall@10 = **0.0**
- doc_recall@10 = **0.0**
- primeiro chunk do doc no top-100: rank `None`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

### ORACLE_EXPANSION

**Query:** Qual é a finalidade metodológica do PRORET Submódulo 2.4 nos processos de revisão tarifária periódica das concessionárias de distribuição?

- passage_recall@10 = **0.0**
- doc_recall@10 = **0.0**
- primeiro chunk do doc no top-100: rank `None`
- primeiro chunk passando matching: rank `None`
- chunk perfeito (cov 1.0): **não entrou no top-100**

---

## Comparação antes/depois

Sobe ↑ ou desce ↓ no chunk perfeito (rank) vs ORIGINAL:

| qid | ORIGINAL rank | GENERIC rank | ORACLE rank |
|---|---|---|---|
| gt-0005 | fora_pool | fora_pool | fora_pool |
| gt-0025 | fora_pool | fora_pool | 41 ↑↑ |
| gt-0027 | fora_pool | fora_pool | fora_pool |
