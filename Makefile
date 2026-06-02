# =============================================================================
# Makefile — atalhos para comandos comuns do projeto
# =============================================================================
# Uso:
#   make install              → instala todas as dependências (dev + ingestão)
#   make test                 → roda testes
#   make lint                 → checa estilo
#   make format               → formata código com black
#   make ingest-atos          → coleta atos normativos (cedoc/ + Power BI)
#   make ingest-leis          → coleta as 4 leis estruturantes
#   make ingest-procedimentos → coleta PRODIST, PRORET, Regras de Transmissão
#   make ingest-rede          → coleta Procedimentos de Rede (ONS)
#   make ingest-manuais       → coleta manuais do gov.br
#   make ingest-all           → coleta todas as fontes (PyMuPDF, merge com Hub)
#   make benchmark-docling    → coleta amostra com Docling (benchmark de extração)
# =============================================================================

fonte ?= procedimentos-rede
amostra ?= 10

install:
	pip3 install -r requirements-dev.txt

test:
	pytest tests/ -v

lint:
	flake8 src/

format:
	black src/ tests/

ingest-atos:
	python3 -m src.ingestion.run --fonte atos

ingest-leis:
	python3 -m src.ingestion.run --fonte leis

ingest-procedimentos:
	python3 -m src.ingestion.run --fonte procedimentos

ingest-rede:
	python3 -m src.ingestion.run --fonte procedimentos-rede

ingest-manuais:
	python3 -m src.ingestion.run --fonte manuais

ingest-all:
	python3 -m src.ingestion.run --todas

validate-corpus:
	python3 scripts/validate_corpus.py

benchmark-pymupdf4llm:
	python3 -m src.ingestion.run --todas --estrategia pymupdf4llm --limpar-estrutura
