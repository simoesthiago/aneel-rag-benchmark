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
    - O que é CONSTANTE (URLs, nomes de modelo) fica neste arquivo, visível

Como usar
---------
    from src.config.settings import (
        ANEEL_CEDOC_URL,
        LEIS_ESTRUTURANTES,
        get_hf_token,
    )

    response = requests.get(f"{ANEEL_CEDOC_URL}/ren20211000.pdf")
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
# Credenciais (vêm do .env — NUNCA hardcoded)
# -----------------------------------------------------------------------------
# Funções (não constantes) porque queremos LAZY LOADING: o erro só dispara
# quando alguém realmente precisa do token. Assim, rodar testes que não tocam
# o HuggingFace funciona mesmo sem o .env configurado.
def get_hf_token() -> str:
    """Token do HuggingFace Hub. Necessário para upload de datasets/índices."""
    return _get_required("HF_TOKEN")


def get_llm_api_key() -> str:
    """Chave da API do LLM.

    Preferimos `OPENAI_API_KEY`, nome padrão do SDK da OpenAI. `LLM_API_KEY`
    fica como compatibilidade com os primeiros testes de avaliação LLM.
    """
    value = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    placeholders = {"sua_chave_aqui", "seu_token_aqui", "your_api_key_here"}
    if not value or value.strip().lower() in placeholders:
        raise RuntimeError(
            "Defina OPENAI_API_KEY no .env para usar geração/juiz LLM. "
            "LLM_API_KEY ainda é aceito como fallback temporário."
        )
    return value


def get_cohere_api_key() -> str:
    """Chave da Cohere API. Usada pelo reranker (Camada 3 → Sprint 7)."""
    value = os.environ.get("COHERE_API_KEY")
    placeholders = {"sua_chave_aqui", "seu_token_aqui", "your_api_key_here"}
    if not value or value.strip().lower() in placeholders:
        raise RuntimeError(
            "Defina COHERE_API_KEY no .env para usar o reranker da Cohere."
        )
    return value


def get_openai_api_key() -> str:
    """
    Chave da OpenAI API.

    Preferimos `OPENAI_API_KEY`, que é o nome padrão do SDK da OpenAI.
    `LLM_API_KEY` fica como fallback temporário para compatibilidade com o
    projeto antes da Camada 2.2.
    """
    value = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    placeholders = {"sua_chave_aqui", "seu_token_aqui", "your_api_key_here"}
    if not value or value.strip().lower() in placeholders:
        raise RuntimeError(
            "Defina OPENAI_API_KEY no .env para usar embeddings via API. "
            "LLM_API_KEY ainda é aceito como fallback temporário."
        )
    return value


# -----------------------------------------------------------------------------
# Repositórios e modelos (configuráveis, mas com default sensato)
# -----------------------------------------------------------------------------
HF_DATASET_REPO: str = _get_optional(
    "HF_DATASET_REPO",
    "simoesthiago/aneel-corpus",
)
# Gerador da Camada 3.5: o smoke usa GPT-5.4 Mini por equilibrar custo e
# qualidade em respostas regulatórias curtas com JSON estruturado.
LLM_MODEL: str = _get_optional("LLM_MODEL", "gpt-5.4-mini")

# Juiz da Camada 4 (faithfulness, answer_correctness): mantemos um nível acima
# do gerador para o sinal ser discriminativo, sem inflar custo (1 chamada por
# pergunta, igual ao gerador).
LLM_JUDGE_MODEL: str = _get_optional("LLM_JUDGE_MODEL", "gpt-5.4-mini")

# Reprodutibilidade: temperatura 0 para o gerador (resposta determinística sobre
# norma) e um teto de tokens generoso o bastante para resposta + tabela de
# citações sem cortar.
LLM_GENERATION_TEMPERATURE: float = float(
    _get_optional("LLM_GENERATION_TEMPERATURE", "0")
)
LLM_GENERATION_MAX_TOKENS: int = int(_get_optional("LLM_GENERATION_MAX_TOKENS", "800"))
LLM_REQUEST_TIMEOUT_SECONDS: float = float(
    _get_optional("LLM_REQUEST_TIMEOUT_SECONDS", "60")
)

EMBEDDING_PROVIDER: str = _get_optional("EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL: str = _get_optional("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_BATCH_SIZE: int = int(_get_optional("EMBEDDING_BATCH_SIZE", "100"))
COHERE_RERANK_MODEL: str = _get_optional(
    "COHERE_RERANK_MODEL",
    "rerank-multilingual-v3.0",
)


# -----------------------------------------------------------------------------
# Vector store (Camada 2.3)
# -----------------------------------------------------------------------------
# Baseline FAISS exato: IndexFlatIP + vetores L2-normalizados. Inner product
# sobre vetores normalizados é matematicamente equivalente a cosine similarity,
# então este é o índice mais simples e auditável para começar o benchmark.
# Índices aproximados (IVF, HNSW, PQ) ficam para uma etapa posterior, depois
# que o baseline exato estiver validado.
FAISS_INDEX_TYPE: str = "IndexFlatIP"
FAISS_METRIC: str = "ip"
VECTORSTORE_HUB_PREFIX: str = "data/vectorstores"


# -----------------------------------------------------------------------------
# Ground truth de avaliação (Camada 4 / eixo de avaliação)
# -----------------------------------------------------------------------------
GROUND_TRUTH_HUB_PREFIX: str = "data/evaluation/ground_truth"
# Fase 3: GT v2 completo (any_of 3a/3b + correções 3c) promovido a default,
# publicado no Hub como `retrieval-50-v2`. A v1 (`retrieval-50`) fica
# preservada. (O intermediário incompleto 3a/3b foi retirado e consolidado
# nesta v2 completa; seu conteúdo está preservado no histórico Git.)
GROUND_TRUTH_VERSION: str = _get_optional(
    "GROUND_TRUTH_VERSION",
    "retrieval-50-v2",
)


# -----------------------------------------------------------------------------
# Constantes do domínio (fixas no código — não são segredos)
# -----------------------------------------------------------------------------

# --- Fonte 1: Atos normativos (Power BI + cedoc/) ---
# Portal da ANEEL onde os PDFs ficam hospedados.
ANEEL_CEDOC_URL: str = "https://www2.aneel.gov.br/cedoc"

# Endpoint da API REST do Power BI "Gestão do Estoque Regulatório".
# O Power BI é o índice mestre: lista todos os atos normativos com metadados
# (situação vigente/revogada, ementa, assunto). O diretório cedoc/ retorna 403.
ANEEL_POWERBI_URL: str = (
    "https://wabi-south-central-us-api.analysis.windows.net"
    "/public/reports/querydata?synchronous=true"
)

# Tipos de ato normativo publicados no CEDOC.
ANEEL_DOC_TYPES: dict[str, str] = {
    "ren": "Resolução Normativa",
    "reh": "Resolução Homologatória",
    "rea": "Resolução Autorizativa",
    "res": "Resolução",
    "dea": "Despacho",
    "por": "Portaria",
}

# Range temporal do corpus. A ANEEL existe desde 1996 (Lei 9.427/1996).
ANEEL_YEAR_RANGE: tuple[int, int] = (1996, 2026)

# --- Fonte 2: Procedimentos regulatórios ---
# 2a. PRODIST, PRORET e Regras de Transmissão (GitLab público da ANEEL)
#   - PRODIST (distribuição) → procreg/prodist/
#   - PRORET (tarifário) → procreg/proret/
#   - Regras de Transmissão → procreg/regtransm/
ANEEL_GITLAB_URL: str = "https://git.aneel.gov.br"
ANEEL_GITLAB_PROJECT: str = "publico/centralconteudo"

# 2b. Procedimentos de Rede (SharePoint público do ONS)
# Embora propostos pelo ONS, são aprovados pela ANEEL (REN 903/2020)
# e obrigatórios para toda distribuidora, geradora e transmissora no SIN.
# O SharePoint permite acesso anônimo (ContentTypeId fixo para os documentos).
# Nota: EE/P&D são RENs (920/2021 e 1045/2022) → scraper_atos.
ONS_PROXY_URL: str = "https://proxyportais.ons.org.br/ons.portalempregado.proxy"

# --- Fonte 3: Manuais, Modelos e Instruções (gov.br) ---
ANEEL_MANUAIS_URL: str = (
    "https://www.gov.br/aneel/pt-br/centrais-de-conteudos"
    "/manuais-modelos-e-instrucoes"
)

# Subcategorias do portal (slugs) — descobertas via inspeção HTML (2026-06-01).
# Inclui subpáginas aninhadas quando existem.
MANUAIS_SUBCATEGORIAS: list[str] = [
    "air",
    "cadastro-unico",
    "cartografia-e-geoprocessamento",
    "composicao-societaria",
    "conselhos-consumidores",
    "distribuicao",
    "envio-de-arquivos",
    "gcem",
    "geracao",
    "geracao/go-gestao-de-outorgas",
    "gestao-de-riscos",
    "gestao-estrategica",
    "informacoes-economico-financeiras",
    "licitacoes-e-contratos",
    "micro-e-minigeracao-distribuida",
    "pdi-aneel",
    "procedimentos-manuais-guias-e-relatorios-do-pdi-aneel",
    "processo-eletronico",
    "seguranca",
    "tarifas",
    "transmissao",
]

# --- Fonte 4: Leis estruturantes (planalto.gov.br) ---
# HTML estático — 4 leis de base do setor elétrico.
LEIS_ESTRUTURANTES: dict[str, str] = {
    "lei-9427-1996": ("https://www.planalto.gov.br/ccivil_03/leis/l9427cons.htm"),
    "lei-8987-1995": ("https://www.planalto.gov.br/ccivil_03/leis/l8987compilada.htm"),
    "lei-9074-1995": ("https://www.planalto.gov.br/ccivil_03/leis/l9074compilada.htm"),
    "lei-13848-2019": (
        "https://www.planalto.gov.br/ccivil_03/" "_ato2019-2022/2019/lei/l13848.htm"
    ),
}


# -----------------------------------------------------------------------------
# Caminhos de runtime
# -----------------------------------------------------------------------------
# Diretório temporário para escrita intermediária durante o pipeline.
# NUNCA criar nada permanente aqui — tudo é publicado no HF Hub no fim.
RUNTIME_TMP_DIR: Path = Path(_get_optional("RUNTIME_TMP_DIR", "/tmp/aneel-rag"))
