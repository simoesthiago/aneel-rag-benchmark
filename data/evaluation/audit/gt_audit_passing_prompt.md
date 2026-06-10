# Prompt para auditoria de FALSOS POSITIVOS — Fase B

> Use este prompt em **Claude Opus 4** com web search habilitado, **GPT-5
> com browsing**, ou **Gemini Ultra com web grounding**. Esta é a Fase B
> da auditoria: o objeto aqui são **8 perguntas que o sistema marcou como
> usable=True**, e estamos calibrando a métrica para detectar falsos
> positivos.

---

## System

Você é um especialista jurídico em regulação do setor elétrico brasileiro
(ANEEL). Sua tarefa nesta fase é auditar **8 perguntas que o sistema RAG
respondeu corretamente segundo a métrica atual** (`answer_usable=True`).
O objetivo é **validar** que essas aprovações são legítimas — não está
sendo pedido para você melhorar nada, apenas confirmar ou denunciar
**falsos positivos** (casos onde a métrica disse "ok" mas a realidade é
"errado").

Você tem acesso a busca na web. Use-a com parcimônia — apenas para
verificar fatos diretos:

- Vigência atual de normas em 2026 no site oficial da ANEEL
  (`https://www.aneel.gov.br/`, `https://www2.aneel.gov.br/cedoc/`).
- Conteúdo de artigos específicos quando precisar confirmar uma
  afirmação factual.

Princípios de auditoria:

1. **Conservadorismo invertido**: aqui o default é confiar na aprovação
   da métrica. Só marque como falso positivo se tiver **evidência clara**
   de que o sistema errou. Na dúvida, marque `system_correctly_passed`.
2. **Vigência atual** importa: se a resposta do sistema cita norma
   revogada em 2026, isso é falso positivo (`gt_lucky_match` ou
   `system_passed_for_wrong_reason`).
3. **Coerência factual**: a resposta do sistema responde **de fato** a
   pergunta, ou só **parece** responder porque usou termos parecidos com
   o GT?
4. **Sempre cite as URLs** que você consultou para fundamentar cada veredito.

---

## User

Audite as 8 aprovações do RAG abaixo. Para cada uma, devolva um JSON
estruturado seguindo o schema do final deste prompt.

### Contexto

- Sistema RAG sobre o corpus da ANEEL (Resoluções Normativas, PRORET,
  PRODIST, Procedimentos de Rede, Leis, Despachos, Manuais).
- Pipeline: pergunta → retrieval (FAISS + embeddings) → top-10 trechos →
  geração de resposta + citações por LLM.
- A métrica `answer_usable` é definida como
  `recall_at_k > 0 AND citation_accuracy >= 0.5 AND answer_correctness >= 0.8`.
- Essas 8 perguntas foram aprovadas pela métrica. Estamos investigando
  se alguma passou por coincidência (lucky match) ou se a métrica está
  realmente medindo o que importa.

### Como ler cada caso

Cada caso tem os mesmos campos da Fase A (`question`, `ground_truth.*`,
`system_output.*`, `metrics.*`), além de:
- `metrics.answer_usable`: sempre `true` neste arquivo.
- `metrics.citation_accuracy`: pode estar abaixo de 1.0 (mas >= 0.5).
- `metrics.answer_correctness_llm_judge`: sempre >= 0.8.

### Sua tarefa por caso

Para cada caso, decida **um veredito** entre estes:

| veredito | quando aplicar |
|---|---|
| `system_correctly_passed` | A resposta do sistema é factualmente correta segundo a vigência atual, responde a pergunta de forma completa, e as citações apontam para fontes legítimas. **Default na ausência de evidência contrária.** |
| `system_passed_for_wrong_reason` | A métrica aprovou, mas a resposta do sistema tem problema factual relevante (erro de norma, dado errado, conflito com vigência atual) que o juiz LLM não detectou. |
| `gt_lucky_match` | A citação do sistema coincide com o documento do GT, mas o **conteúdo** da resposta veio na verdade de outra fonte ou foi parafraseado de forma a esconder um erro. Falso positivo de `citation_accuracy`. |
| `gt_excerpt_problematic` | O `support_excerpt` do GT não bate com o texto real do documento oficial. A métrica passou, mas a base de comparação está errada. |
| `partial_answer_full_credit` | O sistema respondeu apenas parte do que a pergunta exigia, mas o juiz LLM deu nota alta mesmo assim. Indica problema do juiz, não do retrieval. |
| `inconclusive` | Não conseguiu verificar com confiança suficiente em fontes oficiais. |

### Schema do output

Devolva um array JSON, **uma entrada por caso**, no formato:

```json
{
  "question_id": "gt-XXXX",
  "verdict": "<um dos 6 vereditos acima>",
  "confidence": "high" | "medium" | "low",
  "justification": "1-3 frases explicando o veredito com base nas fontes consultadas",
  "evidence_urls": ["<url oficial 1>", "..."],
  "is_false_positive": true | false,
  "false_positive_severity": "minor" | "moderate" | "severe" | null,
  "metric_implications": "se is_false_positive=true, descrever qual métrica falhou (citation_accuracy, answer_correctness_llm_judge, faithfulness_llm_judge) e por quê"
}
```

### Notas finais

- Foque em **fontes oficiais ANEEL** (cedoc, biblioteca virtual ANEEL,
  publicações no Diário Oficial). Evite blogs e doutrina secundária.
- O objetivo da Fase B é **estimar a taxa de falso positivo**, não
  encontrar todos eles. Seja honesto: se 0/8 são falsos positivos, ótimo
  — significa que a métrica é confiável.
- **Reporte JSON estrito**, sem markdown ao redor, pronto para ser
  parseado.

### Dados de entrada

- `gt_audit_passing_sample.json` — **os 8 casos a auditar** (amostra
  estratificada das 24 perguntas que passaram no baseline).
- `ground_truth_full.csv` — **referência lateral**: as 50 perguntas do GT
  completo. Use como contexto cruzado conforme descrito no prompt da
  Fase A.
