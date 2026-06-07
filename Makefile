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
        validate-chunks validate-ground-truth validate-ground-truth-hub \
        publish-ground-truth chunk-all embeddings-sample \
        vectorstore-sample vectorstore-main vectorstore-all \
        validate-vectorstore validate-vectorstore-all \
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
	@echo "    make validate-chunks    Confere chunks publicados no Hub"
	@echo "    make validate-ground-truth Confere ground truth retrieval-50 local"
	@echo "    make validate-ground-truth-hub Confere ground truth retrieval-50 publicado"
	@echo "    make validate-vectorstore-all Confere as 12 vector stores no Hub"
	@echo "    make publish-ground-truth Publica ground truth retrieval-50 no HuggingFace Hub"
	@echo ""
	@echo "  PROCESSAMENTO"
	@echo "    make chunk-all              Gera e publica todos os chunks"
	@echo "    make embeddings-sample      Testa embeddings offline em amostra"
	@echo "    make vectorstore-sample     Smoke barato da vector store (hash, baixa chunks do Hub)"
	@echo "    make vectorstore-main       Gera e publica vector store principal (large+article-aware+markdown)"
	@echo "    make vectorstore-all        Gera e publica a matriz completa de vector stores"
	@echo "                                Use SKIP_EXISTING=0 para forçar regeração"
	@echo "    make validate-vectorstore   Valida vector store publicada no Hub"
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

PYTHON ?= .venv/bin/python

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

validate-chunks:
	python3 scripts/validate_chunks.py

validate-ground-truth:
	python3 scripts/validate_ground_truth.py

validate-ground-truth-hub:
	python3 scripts/validate_ground_truth.py --hub

publish-ground-truth:
	python3 scripts/publish_ground_truth.py

# Valida a vector store principal publicada no Hub (5 consultas-canário).
# Para outras combinações, passar PROVIDER/MODEL/STRATEGY/METODO.
PROVIDER ?= openai
MODEL ?= text-embedding-3-large
STRATEGY ?= article-aware
METODO ?= markdown

validate-vectorstore:
	python3 scripts/validate_vectorstore.py \
		--provider $(PROVIDER) \
		--model $(MODEL) \
		--chunk-strategy $(STRATEGY) \
		--metodo-extracao $(METODO)

validate-vectorstore-all:
	python3 scripts/validate_vectorstores.py

# ------------------------------------------------------------------------------
# AVALIAÇÃO — CAMADA 4 (benchmark de retrieval)
# ------------------------------------------------------------------------------

# Smoke barato: 2 perguntas × 1 configuração. Útil pra validar o pipeline
# antes de pagar embeddings da matriz completa.
benchmark-retrieval-smoke:
	$(PYTHON) scripts/run_benchmark.py \
		--top-k 5 \
		--limit-configs 1 \
		--limit-questions 2

# Roda as 50 perguntas × 16 configurações. Custa embeddings de query OpenAI
# (50 perguntas × 2 modelos = 100 embeddings de query).
benchmark-retrieval:
	$(PYTHON) scripts/run_benchmark.py --top-k 10

# Opt-in: dobra para 32 configs adicionando variantes +rerank (Cohere Rerank 3).
# Exige COHERE_API_KEY no .env. Pool de candidatos = 100 conforme diagnóstico
# (rerank_pool_comparison.md): pool 50 deixa trechos profundos fora do alcance,
# pool 100 sobe passage_recall +4 pp ao custo de doc_recall -2 pp.
# Custo Cohere: 768 chamadas (48 perguntas × 16 configs). Cabe no trial,
# MAS trial limita 10 req/min — leva ~80 min mesmo com retry. Para uma
# config só com rerank, use
# scripts/diagnostics/diagnose_rerank_best_pool100.py.
# Saída separada do baseline (não sobrescreve results.csv original).
benchmark-retrieval-rerank:
	$(PYTHON) scripts/run_benchmark.py --top-k 10 --rerank \
		--rerank-candidates-k 100 \
		--output-dir data/evaluation/results/retrieval-50-rerank

# ------------------------------------------------------------------------------
# PROCESSAMENTO — CAMADA 2
# ------------------------------------------------------------------------------

chunk-all:
	python3 -m src.chunking.run --estrategia todas --metodo-extracao todos --publicar

embeddings-sample:
	python3 -m src.embeddings.run --provider hash --chunk-strategy fixed-size --metodo-extracao markdown --amostra 20

# Smoke barato da Camada 2.3: provider hash, sem custo OpenAI.
# Ainda baixa chunks do HuggingFace Hub, então exige rede.
vectorstore-sample:
	python3 -m src.vectorstore.run \
		--provider hash \
		--chunk-strategy article-aware \
		--metodo-extracao markdown \
		--amostra 100

# Vector store principal: OpenAI large + article-aware + markdown.
# Entrega mínima da Camada 2.3. Custa cerca de US$ por geração; rode com cuidado.
vectorstore-main:
	python3 -m src.vectorstore.run \
		--provider openai \
		--model text-embedding-3-large \
		--chunk-strategy article-aware \
		--metodo-extracao markdown \
		--publicar

VECTORSTORE_MODELS := text-embedding-3-large text-embedding-3-small
VECTORSTORE_STRATEGIES := fixed-size article-aware hierarchical-child
VECTORSTORE_METODOS := markdown texto
SKIP_EXISTING ?= 1

# Matriz completa da Camada 2.3: 2 modelos × 3 estratégias × 2 métodos.
# Default: pula combinações já publicadas no HuggingFace Hub.
# Para forçar a matriz completa do zero: make vectorstore-all SKIP_EXISTING=0
vectorstore-all:
	@echo "Gerando/publicando matriz completa de vector stores OpenAI."
	@echo "Modelos: $(VECTORSTORE_MODELS)"
	@echo "Estratégias: $(VECTORSTORE_STRATEGIES)"
	@echo "Métodos: $(VECTORSTORE_METODOS)"
	@echo "Skip existentes: $(SKIP_EXISTING)"
	@set -e; \
	skip_flag=""; \
	if [ "$(SKIP_EXISTING)" != "0" ]; then \
		skip_flag="--skip-existing"; \
	fi; \
	for model in $(VECTORSTORE_MODELS); do \
		for strategy in $(VECTORSTORE_STRATEGIES); do \
			for metodo in $(VECTORSTORE_METODOS); do \
				echo ""; \
				echo "==> provider=openai model=$$model strategy=$$strategy metodo=$$metodo"; \
				python3 -m src.vectorstore.run \
					--provider openai \
					--model $$model \
					--chunk-strategy $$strategy \
					--metodo-extracao $$metodo \
					--publicar \
					$$skip_flag; \
			done; \
		done; \
	done

# ------------------------------------------------------------------------------
# DESENVOLVIMENTO
# ------------------------------------------------------------------------------

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m flake8 src/

format:
	$(PYTHON) -m black src/ tests/

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
