# =============================================================================
# Makefile — atalhos para comandos comuns do projeto
# =============================================================================
# Uso:
#   make install      → instala deps de desenvolvimento (uso local)
#   make install-prod → instala deps completas (uso em Colab/Actions)
#   make test         → roda testes
#   make lint         → checa estilo
#   make format       → formata código com black
# =============================================================================

install:
	pip install -r requirements-dev.txt

install-prod:
	pip install -r requirements.txt

test:
	pytest tests/ -v

lint:
	flake8 src/

format:
	black src/ tests/
