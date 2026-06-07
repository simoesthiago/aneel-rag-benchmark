"""Fase B - Pacote de inspeção manual para o usuário.

Para cada pergunta especificada, monta um relatório com:
- texto da pergunta, expected_answer
- fonte esperada do GT (doc_id, section, support_excerpt, url)
- top-10 chunks que o retriever devolveu (com texto truncado)
- top chunks do doc_id ESPERADO (mesmo que rankeados além do top-10)

Foco padrão: gt-0002 e gt-0027 (balde 1 — doc não aparece no top-10
da melhor config). Inspeção visual permite testar H4 (dupla resposta),
H6 (vocabulário), H11 (versão).

Saída: data/evaluation/results/diagnostic/phase_b_package.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.evaluation.ground_truth import load_ground_truth_hub  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

PERGUNTAS_FOCO = {"gt-0002", "gt-0027"}
TOP_K_PRINCIPAL = 10
TOP_K_EXPANDIDO = 100  # busca no top-100 pelo doc_id esperado

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/phase_b_package.md"
)


def truncate(text: str, n: int = 250) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + " ..."


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    questions = load_ground_truth_hub()
    foco = [
        q for q in questions if str(q.get("question_id")) in PERGUNTAS_FOCO
    ]
    print(
        f"  {len(foco)} pergunta(s) de foco carregada(s).", file=sys.stderr
    )

    print("Carregando melhor config ...", file=sys.stderr)
    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
    )

    lines: list[str] = []
    lines.append("# Fase B — Pacote de Inspeção Manual\n")
    lines.append(
        "Para cada pergunta abaixo, abra o PDF do documento ESPERADO e "
        "responda às perguntas no final de cada seção. As respostas vão "
        "informar quais das hipóteses H4 (dupla resposta), H6 "
        "(vocabulário) ou H11 (versão errada) explicam a falha.\n"
    )
    lines.append(
        "**Config usada:** text-embedding-3-large + fixed-size + "
        "markdown + flat (a melhor da matriz, recall@10=0.77 / "
        "doc_recall@10=0.854).\n"
    )

    for q in foco:
        qid = str(q.get("question_id"))
        pergunta_texto = str(q.get("question") or "")
        expected = str(q.get("expected_answer") or "")
        sources = list(q.get("relevant_sources") or [])

        print(f"Recuperando top-{TOP_K_EXPANDIDO} para {qid} ...",
              file=sys.stderr)
        chunks = retriever.retrieve(
            q["question"], top_k=TOP_K_EXPANDIDO
        )

        # Documentos únicos no top-K_PRINCIPAL e seus ranks
        ranks_doc: dict[str, int] = {}
        for rank, c in enumerate(chunks, start=1):
            doc = str(c.get("document_id") or "")
            if doc and doc not in ranks_doc:
                ranks_doc[doc] = rank

        lines.append(f"\n---\n\n## {qid}\n")
        lines.append(f"**Pergunta:** {pergunta_texto}\n")
        lines.append(f"**Resposta esperada (GT):** {expected}\n")

        # Detalhes da(s) fonte(s) esperada(s)
        lines.append("### Fonte esperada (ground truth)\n")
        for i, src in enumerate(sources, start=1):
            doc_id = str(src.get("document_id") or "")
            titulo = str(src.get("titulo") or "")
            section = str(src.get("section_label") or "")
            excerpt = str(src.get("support_excerpt") or "")
            url = str(src.get("url") or "")
            cit = str(src.get("citation_label") or "")
            rank_no_top100 = ranks_doc.get(doc_id, None)
            posicao_text = (
                f"chunk do mesmo doc aparece em rank "
                f"{rank_no_top100} (no top-{TOP_K_EXPANDIDO})"
                if rank_no_top100 is not None
                else f"**doc não aparece nem no top-{TOP_K_EXPANDIDO}**"
            )

            lines.append(f"**Fonte #{i}**")
            lines.append(f"- `document_id`: `{doc_id}`")
            lines.append(f"- Título: {titulo}")
            lines.append(f"- Citação: {cit}")
            lines.append(f"- Section label: `{section}`")
            lines.append(f"- URL: {url}")
            lines.append(f"- Support excerpt: > {truncate(excerpt, 400)}")
            lines.append(f"- Posição no retrieval: **{posicao_text}**")
            lines.append("")

        # Top-10 chunks devolvidos pelo retriever
        lines.append(
            f"### Top-{TOP_K_PRINCIPAL} chunks devolvidos pela melhor "
            "config (o que o sistema achou que era relevante)\n"
        )
        lines.append(
            "| rank | document_id | titulo | texto (preview) |"
        )
        lines.append("|---:|---|---|---|")
        for rank, c in enumerate(chunks[:TOP_K_PRINCIPAL], start=1):
            doc_id = str(c.get("document_id") or "")
            titulo = str(c.get("titulo") or "")[:50]
            texto = truncate(c.get("texto") or "", 180)
            # Esconde pipes para não quebrar tabela markdown
            texto = texto.replace("|", "\\|")
            titulo = titulo.replace("|", "\\|")
            lines.append(f"| {rank} | `{doc_id}` | {titulo} | {texto} |")

        # Perguntas para o usuário
        lines.append("\n### Suas perguntas para inspecionar este caso\n")
        lines.append(
            "1. **H4 (dupla resposta):** os documentos que apareceram no "
            "top-10 (lista acima) também respondem a pergunta? Se sim, "
            "qual deles tem a resposta mais relevante?"
        )
        lines.append(
            "2. **H6 (vocabulário):** se você reescrever a pergunta usando "
            "exatamente os termos do título/ementa do documento esperado, "
            "ela ainda soa natural? Que palavras-chave do documento "
            "esperado a pergunta atual NÃO usa?"
        )
        lines.append(
            "3. **H11 (versão):** o documento esperado ainda está vigente "
            "em 2026? Foi revogado/substituído por outra norma? Se sim, "
            "qual?"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nPacote salvo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
