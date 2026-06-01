# =============================================================================
# Makefile — atalhos para comandos comuns do projeto
# =============================================================================
# Uso:
#   make install          → instala todas as dependências (dev + ingestão)
#   make test             → roda testes
#   make lint             → checa estilo
#   make format           → formata código com black
#   make ingest wave=2    → roda o pipeline de ingestão (requer .env com HF_TOKEN)
# =============================================================================

wave ?= 2

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

lint:
	flake8 src/

format:
	black src/ tests/

ingest:
	python -m src.ingestion.run_wave --wave $(wave)
