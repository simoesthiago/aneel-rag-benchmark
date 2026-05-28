# DECISIONS.md — Registro de Decisões de Arquitetura

Cada decisão documenta: contexto, opções avaliadas, escolha e motivo.
O valor está em entender o **por quê**, não só o **o quê**.

---

## [2026-05-28] Infraestrutura zero-custo como premissa do projeto

**Contexto:** projeto de portfólio com orçamento zero; precisa ser demonstrável publicamente.

**Opções avaliadas:**
- AWS/GCP/Azure — custo real, cartão de crédito, não público por padrão
- HuggingFace Hub + Colab + GitHub Actions — gratuito, público, integrado

**Decisão:** HuggingFace Hub para armazenamento, Colab para desenvolvimento, GitHub Actions para produção recorrente.

**Motivo:** zero custo operacional + visibilidade de portfólio. Dataset, índices e chatbot acessíveis via link público. Demonstra pensamento de manutenção (Actions = atualização automática) sem infra local.

---

## [2026-05-28] Dados nunca tocam a máquina local

**Contexto:** PDFs da ANEEL são pesados; índices FAISS crescem com o corpus.

**Opções avaliadas:**
- Baixar dados localmente para desenvolvimento mais ágil
- Processar em memória no Colab e publicar direto no HF Hub

**Decisão:** Colab processa em memória → publica no HF Hub. Zero dados locais.

**Motivo:** `*.pdf`, `*.parquet`, `*.faiss` no `.gitignore` como garantia estrutural. Repositório Git contém apenas código — isso é o padrão correto de MLOps.

---

## [2026-05-28] FAISS como vector store (arquivo, sem servidor)

**Contexto:** comparar estratégias de RAG exige múltiplos índices vetoriais.

**Opções avaliadas:**
- Pinecone / Weaviate / Qdrant — requerem servidor, têm custo ou limite de plano gratuito
- ChromaDB — local, mas não portável entre Colab e HF Spaces sem workaround
- FAISS (arquivo) — índice salvo como `.faiss`, carregado na memória quando necessário

**Decisão:** FAISS com índice salvo no HF Hub.

**Motivo:** sem servidor, zero custo, index é artefato reproduzível (pode ser baixado e inspecionado). HF Spaces baixa o index na inicialização — simples e portável.

---

## [2026-05-28] Parquet como formato de dados estruturados

**Contexto:** textos extraídos dos PDFs precisam de formato de armazenamento tabular.

**Opções avaliadas:**
- CSV — sem tipagem, sem compressão, não suporta listas
- JSON Lines — verboso, sem schema enforcement
- Parquet — colunar, comprimido, tipado, suportado nativamente por pandas/HF datasets

**Decisão:** Parquet.

**Motivo:** padrão de mercado para dados tabulares em ML. `datasets` da HuggingFace lê Parquet nativamente — facilita publicação e consumo do corpus.

---

## [2026-05-28] Scraping via índice do portal (não enumeração de URL)

**Contexto:** RENs têm numeração não-sequencial (gaps, prefixos especiais como `bren`).

**Opções avaliadas:**
- Enumerar URLs por ano/número — simples, mas falha em gaps e variações de formato
- Scraping do índice do portal CEDOC — captura metadados estruturados (ementa, situação, data) junto com o link real do PDF

**Decisão:** scraping do índice.

**Motivo:** metadados (número, ementa, situação `vigente/revogada`, data) são essenciais para o benchmark. Sem eles, o corpus é uma coleção de textos sem contexto — impossível construir perguntas de avaliação realistas.

---

## [2026-05-28] Separar requirements por ambiente (prod vs. dev)

**Contexto:** Python 3.14 local não tem wheels pré-compiladas para PyMuPDF e faiss-cpu.

**Opções avaliadas:**
- Um único `requirements.txt` com comentários explicando o que instalar onde
- Dois arquivos separados: `requirements.txt` (Colab/Actions) e `requirements-dev.txt` (local)

**Decisão:** dois arquivos separados.

**Motivo:** `make install` local nunca vai tentar compilar PyMuPDF. `make install-prod` no Colab instala tudo. Evita confusão de ambiente — anti-padrão documentado no CLAUDE.md.

---

## [2026-05-28] settings.py com lazy loading de tokens

**Contexto:** tokens de API (HF, OpenAI) precisam estar disponíveis para o pipeline, mas não para testes locais.

**Opções avaliadas:**
- Ler `os.environ["HF_TOKEN"]` direto em cada módulo — espalha lógica, erro difícil de rastrear
- Constantes lidas no import de `settings.py` — falha cedo, mas também falha em testes que não precisam de token
- Funções `get_hf_token()` / `get_llm_api_key()` — lazy: erro só quando o token for realmente necessário

**Decisão:** funções lazy em `src/config/settings.py`.

**Motivo:** testes que não tocam HF/OpenAI (ex.: `test_chunking.py`) funcionam sem `.env` configurado. Quem precisar do token chama a função e recebe um `RuntimeError` claro se faltar.
