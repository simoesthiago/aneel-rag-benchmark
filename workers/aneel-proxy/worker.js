/**
 * aneel-proxy — Cloudflare Worker para download do cedoc/ a partir de IPs bloqueados.
 *
 * ⚠️  REQUISITO: Smart Placement deve estar ATIVO neste Worker.
 *     Workers & Pages → aneel-proxy → Settings → Runtime → Placement → Smart
 *
 *     Sem Smart Placement, o Worker executa na edge mais próxima do CHAMADOR
 *     (ex.: GitHub Actions em Azure US → edge americana → cedoc/ bloqueia).
 *     Com Smart Placement, o Worker executa perto do DESTINO (cedoc/ no Brasil)
 *     → edge brasileira → cedoc/ aceita.
 *
 * Uso: GET /?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf
 * Health: GET /health → "aneel-proxy ok"
 */

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

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    if (incoming.pathname === "/health") {
      return new Response("aneel-proxy ok", {
        headers: { "content-type": "text/plain" },
      });
    }

    const target = incoming.searchParams.get("url");
    if (!target) {
      return new Response(
        "aneel-proxy — use ?url=https://www2.aneel.gov.br/cedoc/....pdf ou /health",
        { status: 400, headers: { "content-type": "text/plain" } },
      );
    }

    let parsed;
    try {
      parsed = new URL(target);
    } catch {
      return new Response("Invalid url", { status: 400 });
    }

    if (
      parsed.protocol !== "https:" ||
      parsed.hostname !== "www2.aneel.gov.br" ||
      !parsed.pathname.startsWith("/cedoc/")
    ) {
      return new Response("Only https://www2.aneel.gov.br/cedoc/* allowed", {
        status: 403,
      });
    }

    const upstream = await fetch(parsed.toString(), {
      method: "GET",
      headers: BROWSER_HEADERS,
      redirect: "follow",
      cf: { cacheTtl: 0 },
    });

    const headers = new Headers(upstream.headers);
    headers.set("x-proxy-worker", "aneel-proxy");
    headers.set("x-upstream-status", String(upstream.status));

    return new Response(upstream.body, {
      status: upstream.status,
      headers,
    });
  },
};
