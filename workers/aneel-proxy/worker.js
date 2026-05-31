/**
 * aneel-proxy — Cloudflare Worker para download do cedoc/ a partir de IPs bloqueados.
 *
 * O cedoc/ (www2.aneel.gov.br) retorna HTTP 403 para IPs de datacenter (Colab,
 * GitHub Actions). Requisições originadas na edge da Cloudflare passam pelo
 * bot management sem o bloqueio de IP.
 *
 * Deploy: ver README.md nesta pasta.
 * Uso: GET https://<worker>.workers.dev/?url=https://www2.aneel.gov.br/cedoc/ren20211000.pdf
 */

export default {
  async fetch(request) {
    const target = new URL(request.url).searchParams.get("url");
    if (!target) {
      return new Response("Missing ?url= parameter", { status: 400 });
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

    return fetch(parsed.toString(), {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      },
    });
  },
};
