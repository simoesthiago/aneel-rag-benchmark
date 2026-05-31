# aneel-gitlab-proxy (Cloudflare Worker)

Proxy para acesso à API do GitLab da ANEEL quando o pipeline roda em IP de
datacenter (GitHub Actions, Google Colab). O `git.aneel.gov.br` bloqueia
conexões de datacenters estrangeiros com timeout — mesmo comportamento do cedoc/.

## ⚠️ Service Placement — passo obrigatório

**Sem Service Placement o Worker não funciona em GitHub Actions.**

A lógica é idêntica ao `aneel-proxy` (cedoc/): por padrão o Worker executa
na edge mais próxima do chamador. Com Service Placement você especifica o
servidor de destino (`git.aneel.gov.br:443`) e a Cloudflare roteia o Worker
para a edge mais próxima desse servidor — que é brasileira.

**Como ativar (uma vez, no dashboard):**

1. Abre [dash.cloudflare.com](https://dash.cloudflare.com)
2. **Workers & Pages** → `aneel-gitlab-proxy`
3. Aba **Settings** → seção **Runtime**
4. **Placement** → lápis → seleciona **Service**
5. Preenche: hostname `git.aneel.gov.br`, port `443`
6. Clica **Deploy**

## Deploy (via dashboard)

1. Conta gratuita em [Cloudflare](https://dash.cloudflare.com/)
2. **Workers & Pages** → **Create** → **Worker**
3. Cole o conteúdo de `worker.js` → **Deploy**
4. Ative **Service Placement** (seção acima)
5. Copie a URL **sem barra no final** (ex.: `https://aneel-gitlab-proxy.<usuario>.workers.dev`)
6. Adicione como secret `ANEEL_GITLAB_PROXY_URL` no GitHub Actions

## Endpoints

- `GET /health` → `"aneel-gitlab-proxy ok"`
- `GET /?url=https://git.aneel.gov.br/api/v4/projects/publico%2Fcentralconteudo/repository/tree` → lista arquivos
- `GET /?url=https://git.aneel.gov.br/api/v4/projects/publico%2Fcentralconteudo/repository/files/...` → download

## Teste manual

```bash
# Health check
curl "https://aneel-gitlab-proxy.<usuario>.workers.dev/health"
# → aneel-gitlab-proxy ok

# Listar raiz do repositório (deve retornar JSON com pastas)
curl "https://aneel-gitlab-proxy.<usuario>.workers.dev/?url=https://git.aneel.gov.br/api/v4/projects/publico%2Fcentralconteudo/repository/tree?per_page=10"
# → JSON com lista de arquivos/pastas
```

## Custo

Free tier: 100k requisições/dia. Os procedimentos regulatórios (~20-30 PDFs)
cabem em menos de 0.1% do limite diário.
