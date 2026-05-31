# aneel-proxy-fly

Proxy HTTP no [Fly.io](https://fly.io) (região GRU/São Paulo) para download do
cedoc/ da ANEEL a partir de IP brasileiro fixo.

## Por que existe?

O cedoc/ (`www2.aneel.gov.br`) bloqueia IPs de datacenter estrangeiros (Azure
US, Google Cloud US). A Cloudflare Worker que tínhamos antes roda na edge mais
próxima do chamador — quando o GitHub Actions chama de Azure US, a edge
americana da Cloudflare é bloqueada pelo cedoc/.

Este proxy roda no Fly.io na região GRU (São Paulo). IP fixo brasileiro →
cedoc/ aceita.

## Endpoints

- `GET /health` → `"aneel-proxy ok"`
- `GET /?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf` → o PDF

## Deploy (uma vez)

```bash
# 1. Instalar flyctl no Mac
brew install flyctl

# 2. Login (abre o browser)
fly auth signup   # primeira vez
# OU
fly auth login    # já tem conta

# 3. Deploy a partir desta pasta
cd proxies/aneel-proxy-fly
fly launch --copy-config --no-deploy   # cria o app, mantém fly.toml local
fly deploy
```

Se o nome `aneel-proxy-br` em `fly.toml` já estiver tomado, ajuste antes do
`fly launch`.

## Testar após deploy

```bash
# Health
curl https://<seu-app>.fly.dev/health
# → aneel-proxy ok

# Download
curl -I "https://<seu-app>.fly.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
# → HTTP/2 200, content-type: application/pdf, content-length: ~2.85 MB
```

## Custos

Free tier do Fly.io (sem cartão obrigatório para subir):
- 3 VMs shared-cpu-1x @ 256MB
- 160h/mês de CPU
- 100GB transfer/mês

A Wave 3 inteira (~1.460 PDFs × ~2MB) usa ~3GB de transfer. Cabe folgado.

`auto_stop_machines = "stop"` no `fly.toml` faz a VM dormir quando ociosa
(acorda em ~1s na primeira request), economizando tempo de CPU.

## Logs e diagnóstico

```bash
fly logs                                 # stream em tempo real
fly status                               # estado do app
fly machine list                         # VMs ativas
```
