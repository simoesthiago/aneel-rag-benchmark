# gt-0027 — reteste com oracle real

Em 1.3-alt, a oracle_expansion automática (LLM) não usou os termos discriminantes. Aqui, query oracle construída manualmente com os termos exigidos.

**Pergunta original:**
> Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão tarifária de distribuidoras?

**Oracle real (manual):**
> No PRORET Submódulo 2.4, qual é a metodologia para definição da taxa regulatória de remuneração de capital e da estrutura de capital regulatória no processo de revisão tarifária periódica das concessionárias de distribuição? Trate de custo de capital.

**Doc esperado:** `proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003`
**Support excerpt:** > Estabelecer metodologia para definição da taxa regulatória de remuneração de capital e estrutura de capital regulatória nos processos de revisão tarifária periódica das concessionárias de distribuição.


## ORIGINAL

| config | passage_recall@10 | doc_recall@10 | chunk_doc rank | match rank | best_cov rank | best_cov |
|---|---:|---:|---:|---:|---:|---:|
| fixed/md/flat | 0.0 | 0.0 | None | None | None | 0.0 |
| fixed/tx/flat | 0.0 | 0.0 | None | None | None | 0.0 |
| article/tx/flat | 0.0 | 0.0 | 25 | None | 25 | 0.312 |
| hier/tx/hier | 0.0 | 0.0 | 40 | None | 40 | 0.312 |
| article/md/flat | 0.0 | 1.0 | 4 | 40 | 40 | 0.75 |
| hier/md/hier | 0.0 | 1.0 | 4 | 42 | 42 | 0.75 |

## ORACLE_REAL

| config | passage_recall@10 | doc_recall@10 | chunk_doc rank | match rank | best_cov rank | best_cov |
|---|---:|---:|---:|---:|---:|---:|
| fixed/md/flat | 1.0 | 1.0 | 5 | 5 | 5 | 1.0 |
| fixed/tx/flat | 1.0 | 1.0 | 2 | 2 | 2 | 1.0 |
| article/tx/flat | 1.0 | 1.0 | 5 | 5 | 5 | 0.875 |
| hier/tx/hier | 1.0 | 1.0 | 3 | 3 | 3 | 0.875 |
| article/md/flat | 1.0 | 1.0 | 5 | 5 | 5 | 0.75 |
| hier/md/hier | 1.0 | 1.0 | 9 | 9 | 9 | 0.75 |

## Delta ORACLE_REAL vs ORIGINAL

| config | passage Δ | best_cov Δ | chunk_doc rank (orig → oracle) |
|---|---:|---:|---|
| fixed/md/flat | +1.00 | +1.00 | None → 5 |
| fixed/tx/flat | +1.00 | +1.00 | None → 2 |
| article/tx/flat | +1.00 | +0.56 | 25 → 5 |
| hier/tx/hier | +1.00 | +0.56 | 40 → 3 |
| article/md/flat | +1.00 | +0.00 | 4 → 5 |
| hier/md/hier | +1.00 | +0.00 | 4 → 9 |

## Veredito

- Configs em que ORIGINAL passa (passage_recall > 0): 0/6
- Configs em que ORACLE_REAL passa: 6/6

→ **H6 (vocabulário) CONFIRMADA** para gt-0027: vocabulário discriminante muda o resultado. Fixável por query expansion realística (não-oracle) só se LLM-rewriter souber inferir os termos sem ver o documento.
