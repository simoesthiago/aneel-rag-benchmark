# aneel-proxy (Cloudflare Worker)

Proxy mínimo para baixar PDFs do `cedoc/` quando o pipeline roda em **IP de datacenter** (Google Colab, GitHub Actions). Nesses ambientes o Cloudflare devolve **HTTP 403** mesmo com `curl_cffi` e URLs corretas.

Em **Mac/rede residencial**, não precisa do Worker — use só `curl_cffi` no `scraper_atos.py`.

## Deploy (uma vez)

1. Conta gratuita em [Cloudflare](https://dash.cloudflare.com/)
2. **Workers & Pages** → **Create** → **Worker**
3. Cole o conteúdo de `worker.js` → **Deploy**
4. Copie a URL **sem barra no final** (ex.: `https://aneel-proxy.seu-usuario.workers.dev`)

## Configurar no projeto

| Onde | Variável | Valor |
|------|----------|--------|
| GitHub Actions | Secret `ANEEL_PROXY_URL` | `https://aneel-proxy....workers.dev` |
| Colab | Secret `ANEEL_PROXY_URL` | mesma URL |
| Local `.env` | (opcional) | só se quiser testar o proxy |

## Teste manual

```bash
curl -I "https://SEU-WORKER.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
```

Deve retornar `HTTP/2 200` e `content-type: application/pdf`.

## Custo

Free tier: 100k requisições/dia — suficiente para Wave 1–3 com folga.
