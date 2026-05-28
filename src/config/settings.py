"""
settings.py — Configurações centralizadas do projeto.

Por que existe este módulo?
---------------------------
Todo código real precisa de configuração: tokens de API, URLs, modelos,
caminhos. Espalhar isso pelos arquivos do projeto (hardcoded) tem 3 problemas:

    1. Segurança — tokens em código vão parar no Git por acidente
    2. Reprodutibilidade — quem clona o projeto não sabe o que configurar
    3. Manutenção — mudar uma URL exige caçar pelo repositório inteiro

A solução padrão de mercado:
    - O que é SEGREDO (tokens, API keys) vive em variáveis de ambiente
      → lidas de um arquivo `.env` local (que está no .gitignore)
      → no Colab, vêm de `google.colab.userdata`
      → no GitHub Actions, vêm de `secrets.SOMETHING`
    - O que é CONSTANTE (URLs, nomes de modelo) fica neste arquivo, visível

Como usar
---------
    from src.config.settings import ANEEL_BASE_URL, get_hf_token

    response = requests.get(ANEEL_BASE_URL + "/algum-endpoint")
    token = get_hf_token()  # só é lido aqui, falha cedo se faltar
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Carrega o arquivo .env (se existir) para dentro de os.environ
# -----------------------------------------------------------------------------
# Procura o .env a partir da raiz do projeto, não do arquivo atual.
# Isso garante que funcione mesmo quando o código é importado de subpastas.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# -----------------------------------------------------------------------------
# Helpers — leitura segura de variáveis de ambiente
# -----------------------------------------------------------------------------
def _get_required(name: str) -> str:
    """
    Lê uma variável de ambiente OBRIGATÓRIA.

    Por que falhar cedo? Se HF_TOKEN não estiver setado, queremos descobrir
    isso quando alguém realmente tentar usá-lo — com mensagem clara —, não
    5 minutos depois de processamento, com erro confuso de "401 Unauthorized".
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Variável de ambiente obrigatória '{name}' não foi definida. "
            f"Configure-a no arquivo .env (ver .env.example) ou no ambiente."
        )
    return value


def _get_optional(name: str, default: str) -> str:
    """Lê uma variável de ambiente opcional, com fallback explícito."""
    return os.environ.get(name) or default


# -----------------------------------------------------------------------------
# Credenciais (vêm do .env / userdata / secrets — NUNCA hardcoded)
# -----------------------------------------------------------------------------
# Funções (não constantes) porque queremos LAZY LOADING: o erro só dispara
# quando alguém realmente precisa do token. Assim, rodar testes que não tocam
# o HuggingFace funciona mesmo sem o .env configurado.
def get_hf_token() -> str:
    """Token do HuggingFace Hub. Necessário para upload de datasets/índices."""
    return _get_required("HF_TOKEN")


def get_llm_api_key() -> str:
    """Chave da API do LLM (OpenAI ou outro)."""
    return _get_required("LLM_API_KEY")


# -----------------------------------------------------------------------------
# Repositórios e modelos (configuráveis, mas com default sensato)
# -----------------------------------------------------------------------------
HF_DATASET_REPO: str = _get_optional("HF_DATASET_REPO", "simoesthiago/aneel-corpus")
LLM_MODEL: str = _get_optional("LLM_MODEL", "gpt-4o-mini")


# -----------------------------------------------------------------------------
# Constantes do domínio (fixas no código — não são segredos)
# -----------------------------------------------------------------------------
# Portal da ANEEL onde os PDFs ficam hospedados.
ANEEL_BASE_URL: str = "https://www2.aneel.gov.br/cedoc"

# Tipos de documento publicados no CEDOC.
# Foco do projeto: Resoluções Normativas ('ren'). Os demais ficam aqui
# como referência caso o escopo seja ampliado no futuro.
ANEEL_DOC_TYPES: dict[str, str] = {
    "ren": "Resolução Normativa",   # core regulatório — foco
    "res": "Resolução",             # decisões administrativas
    "dea": "Despacho",              # atos pontuais
    "por": "Portaria",              # estrutura organizacional
}

# Range temporal do corpus. A ANEEL existe desde 1996 (Lei 9.427/1996).
ANEEL_YEAR_RANGE: tuple[int, int] = (1996, 2026)


# -----------------------------------------------------------------------------
# Caminhos de runtime (válidos só em Colab/Actions — nunca local)
# -----------------------------------------------------------------------------
# Diretório temporário para escrita intermediária durante o pipeline.
# Em Colab é /content/tmp; em GitHub Actions usa $RUNNER_TEMP.
# NUNCA criar nada permanente aqui — tudo é publicado no HF Hub no fim.
RUNTIME_TMP_DIR: Path = Path(_get_optional("RUNTIME_TMP_DIR", "/tmp/aneel-rag"))
