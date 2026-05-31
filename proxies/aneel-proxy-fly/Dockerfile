# Imagem mínima do Node 20 LTS — fetch nativo, sem deps externas
FROM node:20-alpine

WORKDIR /app

# Copia metadata primeiro (cacheia a layer mesmo se server.js mudar)
COPY package.json ./

# Copia o servidor
COPY server.js ./

# Fly.io expõe a porta via env PORT; default 8080
ENV PORT=8080
EXPOSE 8080

# Healthcheck nativo do Docker — Fly.io também tem o dele em fly.toml
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/health || exit 1

CMD ["node", "server.js"]
