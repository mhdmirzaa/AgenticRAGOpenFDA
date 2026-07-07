# MaiStorage frontend — multi-stage, slim, non-root (production-hardening).
# Builder installs all deps + builds; the runner ships only the Next "standalone"
# output (traced runtime deps) — a much smaller final image.

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Next's standalone server.js binds to $HOSTNAME (Docker auto-sets it to the
# container id) — pin it to 0.0.0.0 so it listens on all interfaces, otherwise
# the in-container localhost healthcheck can't reach it and it reads "unhealthy".
ENV HOSTNAME=0.0.0.0 PORT=3000
# Copy only the self-contained standalone server + static assets.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1
CMD ["node", "server.js"]
