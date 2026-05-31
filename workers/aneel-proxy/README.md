# aneel-proxy (Cloudflare Worker)

Proxy para download do cedoc/ quando o pipeline roda em IP de datacenter
(GitHub Actions, Google Colab). O cedoc/ bloqueia qualquer IP de datacenter
com HTTP 403 — IPs residenciais e IPs da Cloudflare (via Smart Placement)
são aceitos.

## ⚠️ Smart Placement — passo obrigatório

**Sem Smart Placement o Worker não funciona em GitHub Actions.**

Por quê? Por padrão, o Worker executa na edge mais próxima de **quem chama**.
Quando o Actions (Azure US) chama o Worker, a edge americana faz o `fetch()` →
cedoc/ vê IP de Cloudflare gringo → bloqueia.

Com Smart Placement ativado, a Cloudflare detecta que o Worker faz `fetch()`
para `www2.aneel.gov.br` (Brasil) e move a execução para a edge brasileira
automaticamente — independente de onde o Actions esteja.

**Como ativar (uma vez, no dashboard):**

1. Abre [dash.cloudflare.com](https://dash.cloudflare.com)
2. **Workers & Pages** → `aneel-proxy`
3. Aba **Settings** → seção **Runtime**
4. **Placement** → clica no lápis → seleciona **Smart** → **Deploy**

Confirmação: `cf-ray` nas respostas deve terminar em `-GIG` (Rio) ou outro
datacenter brasileiro.

## Deploy (uma vez, via dashboard)

1. Conta gratuita em [Cloudflare](https://dash.cloudflare.com/)
2. **Workers & Pages** → **Create** → **Worker**
3. Cole o conteúdo de `worker.js` → **Deploy**
4. Ative **Smart Placement** (seção acima)
5. Copie a URL **sem barra no final** (ex.: `https://aneel-proxy.seu-usuario.workers.dev`)
6. Adicione como secret `ANEEL_PROXY_URL` no GitHub Actions e no Colab

## Endpoints

- `GET /health` → `"aneel-proxy ok"`
- `GET /?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf` → o PDF

## Teste manual

```bash
# 1. Health check
curl "https://SEU-WORKER.workers.dev/health"
# → aneel-proxy ok

# 2. Download (deve retornar HTTP 200 e ~2.85 MB)
curl -sI "https://SEU-WORKER.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
# → HTTP/2 200
# → content-length: 2850741
# → cf-ray: ...-GIG   ← confirma edge brasileira
```

Se `/health` OK mas PDF retorna 403, verifique se Smart Placement está ativo.

## Custo

Free tier: 100k requisições/dia. Wave 3 completa (~1460 PDFs) usa <2% do limite.
