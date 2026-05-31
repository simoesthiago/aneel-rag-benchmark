/**
 * aneel-gitlab-proxy — Cloudflare Worker para acesso à API do GitLab da ANEEL.
 *
 * ⚠️  REQUISITO: Service Placement deve estar configurado para git.aneel.gov.br:443
 *     Workers & Pages → aneel-gitlab-proxy → Settings → Runtime → Placement →
 *     "Service" → hostname: git.aneel.gov.br, port: 443
 *
 *     Sem isso, o Worker executa na edge mais próxima do chamador (Azure US/EU)
 *     e o GitLab da ANEEL recebe timeout. Com Service placement, executa na
 *     edge mais próxima do GitLab (Brasil).
 *
 * Por que existe?
 * ---------------
 * O git.aneel.gov.br bloqueia IPs de datacenter estrangeiros com timeout de
 * conexão — mesmo comportamento do cedoc/. O Worker com Service placement
 * força a execução na edge brasileira, onde o GitLab aceita a conexão.
 *
 * Endpoints:
 *   GET /health → "aneel-gitlab-proxy ok"
 *   GET /?url=https://git.aneel.gov.br/api/v4/projects/... → resposta da API
 *
 * Segurança:
 *   Só aceita URLs de git.aneel.gov.br/api/v4/ — não funciona como open relay.
 */

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    // --- Health check ---
    if (incoming.pathname === "/health") {
      return new Response("aneel-gitlab-proxy ok", {
        headers: { "content-type": "text/plain" },
      });
    }

    const target = incoming.searchParams.get("url");
    if (!target) {
      return new Response(
        "aneel-gitlab-proxy — use ?url=https://git.aneel.gov.br/api/v4/... ou /health",
        { status: 400, headers: { "content-type": "text/plain" } },
      );
    }

    // --- Validação de URL: só API v4 do GitLab da ANEEL é permitida ---
    let parsed;
    try {
      parsed = new URL(target);
    } catch {
      return new Response("Invalid url", { status: 400 });
    }

    if (
      parsed.protocol !== "https:" ||
      parsed.hostname !== "git.aneel.gov.br" ||
      !parsed.pathname.startsWith("/api/v4/")
    ) {
      return new Response("Only https://git.aneel.gov.br/api/v4/* allowed", {
        status: 403,
        headers: { "content-type": "text/plain" },
      });
    }

    // --- Fetch upstream ---
    // A API do GitLab não exige headers especiais — sem TLS fingerprinting.
    const upstream = await fetch(parsed.toString(), {
      method: "GET",
      redirect: "follow",
      cf: { cacheTtl: 0 },
    });

    const headers = new Headers(upstream.headers);
    headers.set("x-proxy-worker", "aneel-gitlab-proxy");
    headers.set("x-upstream-status", String(upstream.status));

    return new Response(upstream.body, {
      status: upstream.status,
      headers,
    });
  },
};
