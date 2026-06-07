"""1.2 — Precisão do oráculo sob threshold 0.30 (matches marginais).

Objetivo: descobrir se os matches que passam APENAS com
SUPPORT_EXCERPT_TOKEN_THRESHOLD=0.30 (e falham em 0.60) são verdadeiros
positivos ou falsos positivos do oráculo de avaliação.

Contexto: A.6 mostrou que baixar threshold de 0.60 para 0.30 sobe
passage_recall de 0.77 para 0.85 na melhor config. Mas só medimos recall.
Threshold mais baixo aceita mais matches "por sorte" — se forem falsos
positivos, o ganho de recall é artefato do oráculo, não melhoria real.

Método:
1. Roda retrieval na melhor config (large+fixed-size+markdown+flat),
   top-10, para as 48 perguntas avaliáveis.
2. Para cada par (chunk, fonte_esperada) com mesmo document_id, calcula
   cobertura de tokens informativos do support_excerpt.
3. Filtra "matches marginais": cobertura em [0.30, 0.60). Esses são
   exatamente os pares que mudam de status quando threshold baixa.
4. LLM-as-judge (gpt-4o-mini): para cada match marginal, julga se o
   chunk realmente sustenta a resposta à pergunta, dado o
   support_excerpt esperado.
5. Reporta precisão: fração de matches marginais que são SIM segundo o
   juiz.

Custo: ~50-150 chamadas gpt-4o-mini, ~$0.05-0.20.

Saída: data/evaluation/results/diagnostic/threshold_precision_audit.json
       + resumo md em threshold_precision_summary.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config.settings import get_openai_api_key  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
)
from src.evaluation.matching import (  # noqa: E402
    section_signature_from_chunk,
    section_signature_from_label,
)
from src.rag.retriever import Retriever  # noqa: E402

TOP_K = 10
LOW_THRESHOLD = 0.30
HIGH_THRESHOLD = 0.60
JUDGE_MODEL = "gpt-4o-mini"

OUT_JSON = Path(
    "data/evaluation/results/diagnostic/threshold_precision_audit.json"
)
OUT_MD = Path(
    "data/evaluation/results/diagnostic/threshold_precision_summary.md"
)

JUDGE_SYSTEM = """\
Você é um avaliador especialista em direito regulatório brasileiro (ANEEL).
Sua tarefa é decidir se um trecho recuperado (chunk) sustenta a mesma
informação necessária para responder uma pergunta, dado o trecho-fonte
esperado pelo gabarito.

Critério rigoroso:
- SIM se o chunk contém a mesma informação essencial do support_excerpt,
  mesmo que com palavras diferentes ou em contexto mais amplo.
- NAO se o chunk apenas compartilha vocabulário com o support_excerpt
  mas trata de um assunto/aspecto diferente, ou se a informação central
  para responder a pergunta NÃO está presente no chunk.
- PARCIAL se o chunk contém parte da informação necessária mas não
  toda — não é suficiente sozinho para responder a pergunta.

Responda APENAS em JSON, sem markdown:
{"veredito": "SIM" | "NAO" | "PARCIAL", "justificativa": "1-2 frases curtas"}
"""


def section_match(chunk: dict, source: dict) -> bool:
    """Reproduz a lógica de _section_matches sem importar privada."""
    chunk_sig = section_signature_from_chunk(chunk)
    source_sig = section_signature_from_label(
        str(source.get("section_label") or "")
    )
    if not source_sig or not chunk_sig:
        return False
    if chunk_sig == source_sig:
        return True
    return source_sig.startswith(chunk_sig + ".") or chunk_sig.startswith(
        source_sig + "."
    )


def coverage(chunk: dict, source: dict) -> tuple[float, int, int]:
    excerpt = str(source.get("support_excerpt") or "")
    excerpt_tokens = informative_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0, 0, 0
    chunk_text = str(chunk.get("texto") or "")
    chunk_tokens = set(informative_tokens(chunk_text))
    hits = sum(1 for t in excerpt_tokens if t in chunk_tokens)
    return hits / len(excerpt_tokens), hits, len(excerpt_tokens)


def call_judge(client, pergunta: str, expected: str, excerpt: str, chunk_text: str) -> dict:
    user_msg = (
        f"PERGUNTA: {pergunta}\n\n"
        f"RESPOSTA ESPERADA: {expected}\n\n"
        f"SUPPORT_EXCERPT ESPERADO:\n{excerpt}\n\n"
        f"CHUNK RECUPERADO:\n{chunk_text}\n"
    )
    for tentativa in range(3):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as exc:
            if tentativa == 2:
                return {
                    "veredito": "ERRO",
                    "justificativa": f"Erro no juiz: {exc}",
                }
            time.sleep(2 * (tentativa + 1))
    return {"veredito": "ERRO", "justificativa": "Sem resposta"}


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    questions = load_ground_truth_hub()
    questions = [
        q
        for q in questions
        if str(q.get("answerability") or "corpus_supported")
        == "corpus_supported"
    ]
    print(f"  {len(questions)} perguntas avaliáveis.", file=sys.stderr)

    print("Carregando melhor config ...", file=sys.stderr)
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
    )

    print(
        f"Recuperando top-{TOP_K} e identificando matches marginais ...",
        file=sys.stderr,
    )

    # Para cada pergunta, encontrar matches marginais (passam em 0.30, não em 0.60)
    marginais: list[dict] = []  # cada item é um (chunk, fonte) marginal
    for q_idx, q in enumerate(questions, start=1):
        qid = str(q.get("question_id") or "")
        pergunta = str(q.get("question") or "")
        expected = str(q.get("expected_answer") or "")
        sources = list(q.get("relevant_sources") or [])

        chunks = retriever.retrieve(q["question"], top_k=TOP_K)
        for rank, chunk in enumerate(chunks, start=1):
            chunk_doc = str(chunk.get("document_id") or "")
            for src in sources:
                src_doc = str(src.get("document_id") or "")
                if src_doc != chunk_doc:
                    continue
                if section_match(chunk, src):
                    # match estrutural — não depende de threshold
                    continue
                cov, hits, total = coverage(chunk, src)
                if LOW_THRESHOLD <= cov < HIGH_THRESHOLD:
                    marginais.append(
                        {
                            "question_id": qid,
                            "question": pergunta,
                            "expected_answer": expected,
                            "support_excerpt": str(
                                src.get("support_excerpt") or ""
                            ),
                            "document_id": chunk_doc,
                            "chunk_rank": rank,
                            "chunk_text": str(chunk.get("texto") or ""),
                            "coverage": round(cov, 3),
                            "tokens_hits": hits,
                            "tokens_total": total,
                            "section_label": str(
                                src.get("section_label") or ""
                            ),
                        }
                    )
        if q_idx % 10 == 0:
            print(f"  {q_idx}/{len(questions)}", file=sys.stderr)

    print(
        f"  {len(marginais)} pares (chunk, fonte) marginais identificados.",
        file=sys.stderr,
    )

    if not marginais:
        print("Nenhum match marginal — nada a julgar.")
        return

    # Conta quantas perguntas únicas têm pelo menos 1 marginal e quais
    qids_marginais = sorted({m["question_id"] for m in marginais})
    print(
        f"  {len(qids_marginais)} perguntas têm pelo menos 1 marginal: "
        f"{qids_marginais}",
        file=sys.stderr,
    )

    # Chamar juiz
    print(
        f"Chamando juiz LLM ({JUDGE_MODEL}) em {len(marginais)} casos ...",
        file=sys.stderr,
    )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai obrigatório") from exc
    client = OpenAI(api_key=get_openai_api_key())

    for i, item in enumerate(marginais, start=1):
        veredito = call_judge(
            client,
            pergunta=item["question"],
            expected=item["expected_answer"],
            excerpt=item["support_excerpt"],
            chunk_text=item["chunk_text"],
        )
        item["judge"] = veredito
        if i % 10 == 0:
            print(
                f"  {i}/{len(marginais)} julgados",
                file=sys.stderr,
            )

    # Estatísticas
    contagem: dict[str, int] = {"SIM": 0, "NAO": 0, "PARCIAL": 0, "ERRO": 0}
    for m in marginais:
        v = str(m["judge"].get("veredito", "ERRO"))
        contagem[v] = contagem.get(v, 0) + 1
    total = sum(contagem.values())

    # Precisão estrita (SIM / total) e tolerante (SIM+PARCIAL / total)
    precisao_estrita = contagem.get("SIM", 0) / total if total else 0
    precisao_tolerante = (
        contagem.get("SIM", 0) + contagem.get("PARCIAL", 0)
    ) / total if total else 0

    # Por pergunta — quais perguntas teriam acerto "real" baixando threshold?
    por_pergunta: dict[str, list[str]] = {}
    for m in marginais:
        por_pergunta.setdefault(m["question_id"], []).append(
            str(m["judge"].get("veredito", "ERRO"))
        )

    # Salvar JSON detalhado
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "judge_model": JUDGE_MODEL,
                "config": "large+fixed-size+markdown+flat",
                "top_k": TOP_K,
                "threshold_low": LOW_THRESHOLD,
                "threshold_high": HIGH_THRESHOLD,
                "n_marginal_pairs": total,
                "n_questions_affected": len(qids_marginais),
                "veredito_counts": contagem,
                "precisao_estrita_SIM": round(precisao_estrita, 3),
                "precisao_tolerante_SIM_OU_PARCIAL": round(
                    precisao_tolerante, 3
                ),
                "items": marginais,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Resumo markdown
    lines: list[str] = []
    lines.append("# 1.2 — Precisão do oráculo sob threshold 0.30\n")
    lines.append(
        "Config testada: text-embedding-3-large + fixed-size + markdown + "
        f"flat. Top-{TOP_K}.\n"
    )
    lines.append(
        f"Juiz: {JUDGE_MODEL}. Pares marginais (cobertura "
        f"[{LOW_THRESHOLD}, {HIGH_THRESHOLD})): **{total}** em "
        f"**{len(qids_marginais)} perguntas**.\n"
    )

    lines.append("\n## Distribuição dos veredictos\n")
    lines.append("| veredito | n | % |")
    lines.append("|---|---:|---:|")
    for v in ("SIM", "PARCIAL", "NAO", "ERRO"):
        n = contagem.get(v, 0)
        pct = n / total * 100 if total else 0
        lines.append(f"| {v} | {n} | {pct:.1f}% |")

    lines.append("\n## Precisão do oráculo permissivo\n")
    lines.append(
        f"- **Estrita (SIM):** {precisao_estrita:.3f} "
        f"— fração de matches marginais que são verdadeiros positivos."
    )
    lines.append(
        f"- **Tolerante (SIM+PARCIAL):** {precisao_tolerante:.3f}"
    )
    lines.append("")
    lines.append(
        "**Interpretação:** quanto maior, mais defensável baixar o "
        "threshold para 0.30. Precisão estrita < 0.5 = oráculo está "
        "ficando permissivo demais."
    )

    lines.append("\n## Por pergunta\n")
    lines.append("| question_id | n_marginais | SIM | PARCIAL | NAO |")
    lines.append("|---|---:|---:|---:|---:|")
    for qid in sorted(por_pergunta):
        vs = por_pergunta[qid]
        lines.append(
            f"| {qid} | {len(vs)} | {vs.count('SIM')} "
            f"| {vs.count('PARCIAL')} | {vs.count('NAO')} |"
        )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Resultado 1.2 ===")
    for v in ("SIM", "PARCIAL", "NAO", "ERRO"):
        n = contagem.get(v, 0)
        pct = n / total * 100 if total else 0
        print(f"  {v:8s}: {n:>3d} ({pct:>5.1f}%)")
    print()
    print(f"Precisão estrita (SIM/total)      : {precisao_estrita:.3f}")
    print(f"Precisão tolerante (SIM+PARCIAL)  : {precisao_tolerante:.3f}")
    print()
    print(f"Detalhe JSON: {OUT_JSON}")
    print(f"Resumo MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
