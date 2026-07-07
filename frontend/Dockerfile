# MaiStorage frontend — [M8]; hardened (non-root) in security-hardening.
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# Run as the built-in non-root `node` user (security item 9).
RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "start"]
