/**
 * aneel-proxy-fly — Proxy HTTP para download do cedoc/ a partir de IP brasileiro.
 *
 * Por que existe?
 * ---------------
 * O cedoc/ (www2.aneel.gov.br) bloqueia IPs de datacenter estrangeiros
 * (Azure US/EU, Google Cloud US). A Cloudflare Worker que tínhamos antes
 * roda na edge mais próxima do CHAMADOR — quando o GitHub Actions chama
 * de Azure US, a edge americana da Cloudflare é bloqueada pelo cedoc/.
 *
 * Este servidor roda no Fly.io na região GRU (São Paulo). Como o IP do
 * proxy é brasileiro e fixo, o cedoc/ aceita as requisições.
 *
 * Endpoints:
 *   GET /health  → "aneel-proxy ok"
 *   GET /?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf → o PDF
 *
 * Implementado em Node.js 20+ puro (fetch nativo, sem deps externas).
 */

import http from "node:http";

const PORT = process.env.PORT || 8080;

// Headers que mimetizam um browser real — ajudam a passar pelo bot
// management do cedoc/ mesmo já vindo de IP brasileiro.
const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  Accept:
    "application/pdf,application/octet-stream;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
  Referer: "https://www.aneel.gov.br/",
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "cross-site",
  "Cache-Control": "no-cache",
};

const server = http.createServer(async (req, res) => {
  const incoming = new URL(req.url, `http://${req.headers.host}`);

  // --- Health check ---
  if (incoming.pathname === "/health") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("aneel-proxy ok");
    return;
  }

  const target = incoming.searchParams.get("url");
  if (!target) {
    res.writeHead(400, { "content-type": "text/plain" });
    res.end(
      "aneel-proxy — use ?url=https://www2.aneel.gov.br/cedoc/....pdf ou /health",
    );
    return;
  }

  // --- Validação de URL: só cedoc/ é permitido ---
  // Evita que o proxy vire um open relay para qualquer URL.
  let parsed;
  try {
    parsed = new URL(target);
  } catch {
    res.writeHead(400, { "content-type": "text/plain" });
    res.end("Invalid url");
    return;
  }

  if (
    parsed.protocol !== "https:" ||
    parsed.hostname !== "www2.aneel.gov.br" ||
    !parsed.pathname.startsWith("/cedoc/")
  ) {
    res.writeHead(403, { "content-type": "text/plain" });
    res.end("Only https://www2.aneel.gov.br/cedoc/* allowed");
    return;
  }

  // --- Fetch upstream ---
  try {
    const upstream = await fetch(parsed.toString(), {
      method: "GET",
      headers: BROWSER_HEADERS,
      redirect: "follow",
    });

    const responseHeaders = {
      "x-proxy-server": "aneel-proxy-fly",
      "x-upstream-status": String(upstream.status),
    };
    // Copia content-type e content-length do upstream
    const ct = upstream.headers.get("content-type");
    const cl = upstream.headers.get("content-length");
    if (ct) responseHeaders["content-type"] = ct;
    if (cl) responseHeaders["content-length"] = cl;

    res.writeHead(upstream.status, responseHeaders);

    // Stream do corpo (PDF pode ter MB) — evita buffer inteiro em RAM
    const reader = upstream.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(value);
    }
    res.end();
  } catch (err) {
    res.writeHead(502, { "content-type": "text/plain" });
    res.end(`Upstream fetch error: ${err.message}`);
  }
});

server.listen(PORT, () => {
  console.log(`aneel-proxy-fly listening on :${PORT}`);
});
