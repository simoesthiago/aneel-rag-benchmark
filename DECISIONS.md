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

## [2026-05-28] Escopo expandido: corpus cobre ecossistema regulatório completo

**Contexto:** o projeto começou focado em Resoluções Normativas (RENs). Investigação com Playwright revelou que o portal ANEEL organiza "Atos Relevantes" em 13 categorias. A questão era: quais categorias incluir no RAG?

**Categorias avaliadas (13 do leis.org/aneel):**
1. Atos publicados - DOU (feed bruto de TODOS os atos no DOU)
2. Atos dos Conselhos e Comitês - MME (ente diferente)
3. Regimento Interno (1 documento — institucional)
4. Lei de Criação da ANEEL (Lei 9.427/1996)
5. Estrutura Regimental (Decreto 2.335)
6. Lei das Concessões (Lei 8.987/1995)
7. Lei das Outorgas (Lei 9.074/1995)
8. Lei das Agências Reguladoras (Lei 13.848/2019)
9. Regras de Prestação - Distribuição (= REN 1000/2021, já coberta via cat. 13)
10. Normas de Organização (administrativo interno)
11. Procedimentos Regulatórios (PRODIST, PRORET, Proc. Rede, EE/P&D, Transmissão)
12. Manuais, Modelos e Instruções (19 subcategorias)
13. Gestão do Estoque Regulatório (Power BI = índice mestre de atos normativos)

**Decisão:** corpus core = categorias 4 + 6 + 7 + 8 + 11 + 12 + 13.

**Motivo:** um RAG que cobre apenas RENs não responde perguntas operacionais ("Como calcular o DEC?", "Qual o modelo de contrato de distribuição?"). Incluir procedimentos regulatórios (PRODIST/PRORET), manuais e as leis de base cria um ecossistema regulatório completo — muito mais valioso como benchmark e como ferramenta real.

**Fora do escopo e motivo:**
- Cat. 1 (DOU): feed bruto enorme; atos normativos já cobertos via cat. 13
- Cat. 2 (MME): ente diferente — Ministério, não ANEEL
- Cat. 3 (Regimento): institucional, baixa demanda
- Cat. 5 (Estrutura): organizacional, raramente consultado
- Cat. 9 (REN 1000): redundante — já será coletada como ato normativo vigente
- Cat. 10 (Normas de Org.): administrativo interno

**Riscos adicionais desta decisão:**
- Cat. 12 (Manuais) tem formatos variados (PDF, Excel, Word) — `extractor.py` mais complexo
- Volume total pode ser centenas de documentos — precisa de checkpointing robusto

---

## [2026-05-28] Power BI como índice de atos normativos (cedoc/ retorna 403)

**Contexto:** a estratégia original era scraping do índice HTML em `www2.aneel.gov.br/cedoc/`. Investigação revelou que o diretório retorna HTTP 403.14 (directory listing disabled).

**Descoberta:** o índice real é o Power BI "Gestão do Estoque Regulatório" (`app.powerbi.com/view?r=eyJrIjoiM2Rj...`), que faz POST para `wabi-south-central-us-api.analysis.windows.net/public/reports/querydata`. Esse relatório expõe ~1.460 atos normativos com metadados (número, ano, tipo, situação, ementa).

**Decisão:** usar a API REST do Power BI como ponto de descoberta, depois baixar PDFs do cedoc/ usando o padrão de URL conhecido.

**Motivo:** é a única forma estruturada de listar os atos normativos da ANEEL. Enumeração cega de URLs não captura metadados (situação vigente/revogada, ementa, assunto).

---

## [2026-05-28] PRODIST/PRORET via GitLab público (git.aneel.gov.br)

**Contexto:** procedimentos regulatórios (PRODIST, PRORET) não estão no Power BI.

**Descoberta:** os módulos do PRODIST e PRORET estão em `git.aneel.gov.br/publico/centralconteudo/` — um GitLab público da ANEEL com API REST acessível.

**Decisão:** coletar procedimentos regulatórios via API REST do GitLab (`/api/v4/projects/.../repository/tree`).

**Motivo:** API estruturada, versionada, com listagem de arquivos — mais confiável que scraping de HTML. Permite atualizações incrementais.

---

## [2026-05-28] settings.py com lazy loading de tokens

**Contexto:** tokens de API (HF, OpenAI) precisam estar disponíveis para o pipeline, mas não para testes locais.

**Opções avaliadas:**
- Ler `os.environ["HF_TOKEN"]` direto em cada módulo — espalha lógica, erro difícil de rastrear
- Constantes lidas no import de `settings.py` — falha cedo, mas também falha em testes que não precisam de token
- Funções `get_hf_token()` / `get_llm_api_key()` — lazy: erro só quando o token for realmente necessário

**Decisão:** funções lazy em `src/config/settings.py`.

**Motivo:** testes que não tocam HF/OpenAI (ex.: `test_chunking.py`) funcionam sem `.env` configurado. Quem precisar do token chama a função e recebe um `RuntimeError` claro se faltar.
