# 1.2 — Precisão do oráculo sob threshold 0.30

Config testada: text-embedding-3-large + fixed-size + markdown + flat. Top-10.

Juiz: gpt-4o-mini. Pares marginais (cobertura [0.3, 0.6)): **73** em **28 perguntas**.


## Distribuição dos veredictos

| veredito | n | % |
|---|---:|---:|
| SIM | 4 | 5.5% |
| PARCIAL | 4 | 5.5% |
| NAO | 65 | 89.0% |
| ERRO | 0 | 0.0% |

## Precisão do oráculo permissivo

- **Estrita (SIM):** 0.055 — fração de matches marginais que são verdadeiros positivos.
- **Tolerante (SIM+PARCIAL):** 0.110

**Interpretação:** quanto maior, mais defensável baixar o threshold para 0.30. Precisão estrita < 0.5 = oráculo está ficando permissivo demais.

## Por pergunta

| question_id | n_marginais | SIM | PARCIAL | NAO |
|---|---:|---:|---:|---:|
| gt-0001 | 2 | 0 | 0 | 2 |
| gt-0003 | 1 | 0 | 0 | 1 |
| gt-0005 | 1 | 0 | 0 | 1 |
| gt-0008 | 1 | 0 | 0 | 1 |
| gt-0009 | 2 | 0 | 0 | 2 |
| gt-0014 | 4 | 1 | 2 | 1 |
| gt-0015 | 2 | 0 | 0 | 2 |
| gt-0016 | 5 | 1 | 0 | 4 |
| gt-0017 | 1 | 0 | 0 | 1 |
| gt-0018 | 2 | 0 | 0 | 2 |
| gt-0019 | 1 | 0 | 0 | 1 |
| gt-0020 | 1 | 0 | 0 | 1 |
| gt-0021 | 4 | 1 | 0 | 3 |
| gt-0022 | 1 | 0 | 0 | 1 |
| gt-0025 | 1 | 0 | 0 | 1 |
| gt-0032 | 4 | 0 | 0 | 4 |
| gt-0033 | 1 | 0 | 0 | 1 |
| gt-0034 | 2 | 0 | 0 | 2 |
| gt-0036 | 1 | 0 | 0 | 1 |
| gt-0037 | 6 | 0 | 0 | 6 |
| gt-0038 | 8 | 1 | 0 | 7 |
| gt-0039 | 4 | 0 | 1 | 3 |
| gt-0040 | 4 | 0 | 0 | 4 |
| gt-0041 | 2 | 0 | 0 | 2 |
| gt-0046 | 2 | 0 | 1 | 1 |
| gt-0047 | 6 | 0 | 0 | 6 |
| gt-0048 | 2 | 0 | 0 | 2 |
| gt-0049 | 2 | 0 | 0 | 2 |
