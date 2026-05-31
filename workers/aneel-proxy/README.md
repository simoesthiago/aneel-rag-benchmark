# aneel-proxy — Cloudflare Worker

Proxy edge para baixar PDFs do `cedoc/` da ANEEL contornando o bot management
do Cloudflare que bloqueia IPs de data center.

## Por quê

O `https://www2.aneel.gov.br/cedoc/` retorna HTTP 403 para qualquer requisição
vinda de IPs de cloud provider (Google Cloud / Colab, Azure / GitHub Actions).
Mesmo `curl_cffi` com `impersonate=chrome120` não resolve — a barreira é por IP,
não por fingerprint.

Cloudflare Workers fazem `fetch()` a partir dos próprios edges da Cloudflare —
hipótese é que esses IPs têm reputação neutra e passam pelo bot management do
próprio cedoc/ (que também é cliente Cloudflare).

Ver `DECISIONS.md` na raiz do projeto para o histórico completo da decisão.

## Deploy via dashboard (sem CLI)

1. Acesse https://dash.cloudflare.com → **Workers & Pages** → **Create**
2. Selecione **Create Worker** → nome: `aneel-proxy`
3. No editor que abrir, **apague o código padrão** e cole o conteúdo de `worker.js`
4. Clique em **Save and Deploy**
5. URL final: `https://aneel-proxy.<seu-username>.workers.dev`

## Verificação rápida

Endpoint de saúde (não toca cedoc/):

```bash
curl https://aneel-proxy.<seu-username>.workers.dev/health
# {"status":"ok","worker":"aneel-proxy","cf_colo":"GRU",...}
```

Teste real (baixa REN 1000/2021):

```bash
curl -I "https://aneel-proxy.<seu-username>.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
# Esperado: HTTP/2 200 com content-type: application/pdf
```

Se `X-Upstream-Status: 200` aparecer → hipótese confirmada, pipeline em
Actions é viável. Se for 403 → cair para ScrapingBee (Plano C).

## Segurança

O Worker tem whitelist estrita:

- Só aceita URLs do hostname `www2.aneel.gov.br`
- Só aceita paths começando com `/cedoc/`
- Qualquer outra URL retorna 403

Isso evita que o Worker se torne open proxy abusável.

## Custo

Free tier da Cloudflare Workers: 100.000 requisições/dia. A Wave 3 completa
(1460 atos) cabe em <2% do limite diário, então mesmo com reindexação semanal
ficamos folgados.
