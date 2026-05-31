/**
 * aneel-proxy — Cloudflare Worker para baixar PDFs do cedoc/ da ANEEL.
 *
 * Por que este Worker existe?
 * ---------------------------
 * O diretório cedoc/ (https://www2.aneel.gov.br/cedoc/) usa Cloudflare Bot
 * Management. Confirmamos empiricamente que ele bloqueia IPs de todos os data
 * centers comuns (Google Cloud / Colab, Azure / GitHub Actions) com HTTP 403,
 * independente de TLS fingerprint ou impersonação de browser.
 *
 * Hipótese: requisições vindas dos próprios edges da Cloudflare têm reputação
 * de IP neutra/positiva (não estão em listas de "data center suspeito") e
 * portanto passam pelo bot management. Este Worker é o teste dessa hipótese
 * e a solução de produção se ela se confirmar.
 *
 * Como usar (do GitHub Actions, do Colab, ou local):
 *   GET https://aneel-proxy.<seu-user>.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf
 *
 * O Worker:
 *   1. Valida que a URL é do domínio www2.aneel.gov.br/cedoc/ (não open proxy)
 *   2. Repassa a requisição com headers que parecem um browser real
 *   3. Retorna o PDF como resposta
 *
 * Custo: 100k requisições/dia no free tier — muito além do necessário.
 */

export default {
  async fetch(request, env, ctx) {
    const requestUrl = new URL(request.url);

    // Endpoint de saúde para diagnóstico rápido
    if (requestUrl.pathname === "/health") {
      return new Response(
        JSON.stringify({
          status: "ok",
          worker: "aneel-proxy",
          cf_colo: request.cf?.colo ?? "unknown",
          message: "Use ?url=https://www2.aneel.gov.br/cedoc/...pdf",
        }),
        { headers: { "content-type": "application/json" } }
      );
    }

    // Parâmetro obrigatório: ?url=...
    const targetUrlStr = requestUrl.searchParams.get("url");
    if (!targetUrlStr) {
      return new Response(
        "Missing required parameter: ?url=https://www2.aneel.gov.br/cedoc/<arquivo>.pdf",
        { status: 400 }
      );
    }

    // Whitelist: só aceita URLs do cedoc/ — não vira open proxy
    let targetUrl;
    try {
      targetUrl = new URL(targetUrlStr);
    } catch {
      return new Response("Invalid URL parameter", { status: 400 });
    }

    if (
      targetUrl.hostname !== "www2.aneel.gov.br" ||
      !targetUrl.pathname.startsWith("/cedoc/")
    ) {
      return new Response(
        "Forbidden: only https://www2.aneel.gov.br/cedoc/ URLs are allowed",
        { status: 403 }
      );
    }

    // Faz o fetch via edge da Cloudflare com headers de browser
    const upstreamResponse = await fetch(targetUrl.toString(), {
      method: "GET",
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://www2.aneel.gov.br/",
      },
    });

    // Repassa o status e o body. Adiciona um header de diagnóstico.
    const responseHeaders = new Headers(upstreamResponse.headers);
    responseHeaders.set("X-Proxy-Worker", "aneel-proxy");
    responseHeaders.set("X-Upstream-Status", String(upstreamResponse.status));

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  },
};
