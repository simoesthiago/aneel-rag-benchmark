# aneel-proxy-fly

> ⚠️ **NÃO USAR PARA cedoc/** — IPs do Fly.io também são bloqueados pelo cedoc/
> com HTTP 403, mesmo na região GRU (São Paulo). O cedoc/ bloqueia **qualquer IP
> de datacenter**, não só estrangeiros. Testado e confirmado em 2026-05-31.
>
> **A solução correta para cedoc/ é o Cloudflare Worker com Smart Placement.**
> Ver `workers/aneel-proxy/README.md`.
>
> Este diretório fica documentado como referência histórica e pode ser útil
> para outros proxies que não dependam do cedoc/.

---

Proxy HTTP no [Fly.io](https://fly.io) (região GRU/São Paulo).

## Por que existe? (histórico)

Tentativa de substituir o Cloudflare Worker depois de descobrirmos que o Worker,
sem Smart Placement, executava na edge mais próxima do chamador (edge americana
quando chamado do GitHub Actions). A hipótese era que um IP fixo brasileiro (Fly.io
GRU) resolveria o problema.

**Por que não funcionou:** o cedoc/ bloqueia IPs de datacenter em geral, não apenas
estrangeiros. O Fly.io GRU tem IPs de datacenter → bloqueado com HTTP 403.

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
