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
# Copy only the self-contained standalone server + static assets.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1
CMD ["node", "server.js"]
