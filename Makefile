# =============================================================================
# Makefile — ANEEL RAG Benchmark
# =============================================================================
#
# Pré-requisitos:
#   1. Python 3.10+
#   2. Conta no HuggingFace com um dataset criado (público ou privado)
#   3. Arquivo .env configurado — copie .env.example e preencha
#
# Fluxo de onboarding (clone → corpus pronto):
#
#   make install            # instala dependências
#   make check-env          # valida .env e acesso ao HuggingFace
#   make ingest-all         # coleta tudo em texto plano  (~2h, IP residencial BR)
#   make benchmark-markdown # re-extrai tudo em Markdown  (~2h, IP residencial BR)
#   make validate-corpus    # confere estrutura do Hub
#
# ⚠️  A ingestão exige IP residencial brasileiro — o cedoc/ da ANEEL bloqueia
#     datacenters. Rode na sua máquina, não em Colab/Actions/cloud.
#
# =============================================================================

.PHONY: help install check-env test lint format \
        ingest-all benchmark-markdown repair-corpus corpus-reset validate-corpus \
        ingest-atos ingest-leis ingest-procedimentos ingest-rede ingest-manuais

# ------------------------------------------------------------------------------
# AJUDA
# ------------------------------------------------------------------------------

help:
	@echo ""
	@echo "ANEEL RAG Benchmark — comandos disponíveis"
	@echo "============================================"
	@echo ""
	@echo "  SETUP"
	@echo "    make install            Instala todas as dependências"
	@echo "    make check-env          Valida .env e acesso ao HuggingFace Hub"
	@echo ""
	@echo "  INGESTÃO (fluxo principal)"
	@echo "    make ingest-all         Coleta todas as fontes em texto plano (baseline)"
	@echo "    make benchmark-markdown Re-extrai tudo em Markdown (segunda estratégia)"
	@echo "    make repair-corpus      Repara pares texto/markdown ausentes no Hub"
	@echo "    make corpus-reset       Apaga o Hub e reconstrói do zero (texto + markdown)"
	@echo ""
	@echo "  VALIDAÇÃO"
	@echo "    make validate-corpus    Confere métricas e estrutura do corpus no Hub"
	@echo ""
	@echo "  DESENVOLVIMENTO"
	@echo "    make test               Roda testes unitários"
	@echo "    make lint               Checa estilo (flake8)"
	@echo "    make format             Formata código (black)"
	@echo ""
	@echo "  INGESTÃO POR FONTE (avançado — para re-rodar uma fonte específica)"
	@echo "    make ingest-atos        Atos normativos (Power BI + cedoc/)"
	@echo "    make ingest-leis        4 leis estruturantes (Planalto)"
	@echo "    make ingest-procedimentos  PRODIST, PRORET, Regras de Transmissão"
	@echo "    make ingest-rede        Procedimentos de Rede (ONS SharePoint)"
	@echo "    make ingest-manuais     Manuais, modelos e instruções (gov.br)"
	@echo ""

# ------------------------------------------------------------------------------
# SETUP
# ------------------------------------------------------------------------------

install:
	pip3 install -r requirements.txt

check-env:
	@echo "Verificando pré-requisitos..."
	@test -f .env || (echo "\n❌ Arquivo .env não encontrado." \
		&& echo "   Copie o exemplo: cp .env.example .env" \
		&& echo "   Depois preencha HF_TOKEN e HF_DATASET_REPO\n" && exit 1)
	@python3 -c "\
from dotenv import load_dotenv; load_dotenv(); \
import os; \
token = os.getenv('HF_TOKEN', ''); \
repo = os.getenv('HF_DATASET_REPO', ''); \
errors = []; \
(not token or token == 'seu_token_aqui') and errors.append('HF_TOKEN não configurado'); \
(not repo or repo == 'seu-usuario/aneel-corpus') and errors.append('HF_DATASET_REPO não configurado'); \
[print(f'❌ {e}') for e in errors]; \
errors and exit(1) or print('✅ .env OK')"
	@python3 -c "\
from dotenv import load_dotenv; load_dotenv(); \
from huggingface_hub import HfApi; import os; \
api = HfApi(token=os.getenv('HF_TOKEN')); \
repo = os.getenv('HF_DATASET_REPO'); \
api.repo_info(repo, repo_type='dataset'); \
print(f'✅ HuggingFace Hub acessível: {repo}')" \
	|| (echo "❌ Não foi possível acessar o HuggingFace Hub." \
		&& echo "   Verifique HF_TOKEN e se o dataset '$$HF_DATASET_REPO' existe." && exit 1)
	@echo "✅ Tudo pronto para rodar a ingestão."

# ------------------------------------------------------------------------------
# INGESTÃO — FLUXO PRINCIPAL
# ------------------------------------------------------------------------------

# Coleta todas as fontes em texto plano e publica no Hub (merge incremental).
# Primeira vez: Hub vazio → sobe tudo. Rodadas seguintes: atualiza incrementalmente.
ingest-all:
	python3 -m src.ingestion.run --todas --estrategia texto

# Re-extrai todas as fontes em Markdown, repara eventuais lacunas texto/markdown
# causadas por rate limit/transientes e valida o corpus final do benchmark.
# Rode DEPOIS de `make ingest-all`.
benchmark-markdown:
	python3 -m src.ingestion.run --todas --estrategia markdown
	python3 -m src.ingestion.repair_missing_extractions
	python3 scripts/validate_corpus.py

# Repara somente documentos que ficaram com uma estratégia de extração faltante.
# Útil quando o cedoc/ aplica rate limit no meio de uma rodada.
repair-corpus:
	python3 -m src.ingestion.repair_missing_extractions
	python3 scripts/validate_corpus.py

# Apaga o Hub e reconstrói do zero com texto + markdown.
# Use apenas quando quiser resetar o corpus por completo (ex.: mudança de schema).
corpus-reset:
	@echo "⚠️  Isso vai apagar o corpus no Hub e reescrever do zero."
	@echo "   Pressione Ctrl+C para cancelar. Aguardando 5s..."
	@sleep 5
	python3 -m src.ingestion.run --todas --estrategia texto --limpar-estrutura
	python3 -m src.ingestion.run --todas --estrategia markdown
	python3 -m src.ingestion.repair_missing_extractions
	python3 scripts/validate_corpus.py

# ------------------------------------------------------------------------------
# VALIDAÇÃO
# ------------------------------------------------------------------------------

validate-corpus:
	python3 scripts/validate_corpus.py

# ------------------------------------------------------------------------------
# DESENVOLVIMENTO
# ------------------------------------------------------------------------------

test:
	pytest tests/ -v

lint:
	flake8 src/

format:
	black src/ tests/

# ------------------------------------------------------------------------------
# INGESTÃO POR FONTE (avançado)
# ------------------------------------------------------------------------------
# Use para re-rodar uma única fonte sem afetar as outras.
# Exemplos:
#   make ingest-atos                            # texto (default)
#   make ingest-atos ESTRATEGIA=markdown        # markdown

ESTRATEGIA ?= texto

ingest-atos:
	python3 -m src.ingestion.run --fonte atos --estrategia $(ESTRATEGIA)

ingest-leis:
	python3 -m src.ingestion.run --fonte leis --estrategia $(ESTRATEGIA)

ingest-procedimentos:
	python3 -m src.ingestion.run --fonte procedimentos --estrategia $(ESTRATEGIA)

ingest-rede:
	python3 -m src.ingestion.run --fonte procedimentos-rede --estrategia $(ESTRATEGIA)

ingest-manuais:
	python3 -m src.ingestion.run --fonte manuais --estrategia $(ESTRATEGIA)
