# aneel-proxy (Cloudflare Worker)

Proxy para download do cedoc/ quando o pipeline roda em IP de datacenter
(GitHub Actions, Google Colab). O cedoc/ bloqueia qualquer IP de datacenter
com HTTP 403 — IPs residenciais e IPs da Cloudflare na edge brasileira
(via Service Placement) são aceitos.

## ⚠️ Service Placement — passo obrigatório

**Sem Service Placement o Worker não funciona em GitHub Actions.**

Por quê? Por padrão, o Worker executa na edge mais próxima de **quem chama**.
Quando o Actions (Azure US) chama o Worker, a edge americana faz o `fetch()` →
cedoc/ vê IP gringo → bloqueia.

Com **Service Placement** você especifica o servidor de destino
(`www2.aneel.gov.br:443`) e a Cloudflare roteia o Worker para a edge mais
próxima desse servidor — que é brasileira.

**Como ativar (uma vez, no dashboard):**

1. Abre [dash.cloudflare.com](https://dash.cloudflare.com)
2. **Workers & Pages** → `aneel-proxy`
3. Aba **Settings** → seção **Runtime**
4. **Placement** → lápis → seleciona **Service**
5. Preenche: hostname `www2.aneel.gov.br`, port `443`
6. Clica **Deploy**

Confirmação: `cf-ray` nas respostas deve terminar em `-GIG` (Rio) ou outro
datacenter brasileiro.

## Deploy (uma vez, via dashboard)

1. Conta gratuita em [Cloudflare](https://dash.cloudflare.com/)
2. **Workers & Pages** → **Create** → **Worker**
3. Cole o conteúdo de `worker.js` → **Deploy**
4. Ative **Service Placement** (seção acima)
5. Copie a URL **sem barra no final** (ex.: `https://aneel-proxy.<usuario>.workers.dev`)
6. Adicione como secret `ANEEL_PROXY_URL` no GitHub Actions

## Endpoints

- `GET /health` → `"aneel-proxy ok"`
- `GET /?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf` → o PDF

## Teste manual

```bash
# 1. Health check
curl "https://aneel-proxy.<usuario>.workers.dev/health"
# → aneel-proxy ok

# 2. Download (deve retornar HTTP 200 e ~2.85 MB)
curl -sI "https://aneel-proxy.<usuario>.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
# → HTTP/2 200
# → content-length: 2850741
# → cf-ray: ...-GIG   ← confirma edge brasileira
```

Se `/health` OK mas PDF retorna 403, verifique se Service Placement está ativo
com `www2.aneel.gov.br:443`.

## Custo

Free tier: 100k requisições/dia. Wave 3 completa (~1460 PDFs) usa <2% do limite.
