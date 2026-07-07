# Deployment

How to ship MaiStorage to production. Pairs with `docs/OPERATIONS.md` (logging /
metrics / alerts / env contract) and `docs/SECURITY.md` (the controls).

## What "production" turns on

The hardened stack comes up with one overlay chain:

```bash
docker compose -f docker-compose.yml \
               -f docker-compose.redis.yml \
               -f docker-compose.prod.yml up --build -d
```

`docker-compose.prod.yml` (over the base) enables **auth + rate limiting + HSTS +
JSON logs**, keeps **Postgres/OpenSearch/Redis off the network** (no published
ports), sets a **Redis password**, and adds a **healthcheck + resource limits +
`restart: unless-stopped`** to every service. Images are **non-root** and **slim**
(backend on `python:3.11-slim`; frontend a multi-stage **Next standalone** build).

## Required environment (from a secrets manager)

Inject at deploy time from AWS Secrets Manager / Doppler / Vault — never commit or
bake into a layer. Full table in `docs/OPERATIONS.md`; the must-haves:

```
OPENAI_API_KEY=...            # LLM + embeddings
API_KEYS=key1,key2            # accepted X-API-Key values (AUTH_ENABLED=1)
BACKEND_API_KEY=key1          # the key the Telegram bot presents
REDIS_PASSWORD=...            # shared cache + rate-limit store
CORS_ORIGINS=https://app.example.com
DATABASE_URL=postgresql+psycopg://app:...@postgres:5432/maistorage
PUBLIC_API_URL=https://api.example.com   # what the browser calls
```

## Build & push images to a registry

```bash
# from repo root
docker build -t REGISTRY/maistorage-backend:$(git rev-parse --short HEAD)  ./backend
docker build -t REGISTRY/maistorage-frontend:$(git rev-parse --short HEAD) ./frontend
docker push REGISTRY/maistorage-backend:TAG
docker push REGISTRY/maistorage-frontend:TAG
```

Point the compose `image:` (or your orchestrator) at the pushed tags instead of
`build:` for immutable deploys.

## Run on a single cloud host

1. Provision a host (≥ 4 vCPU / 8 GB) with Docker + Compose v2.
2. Put the secrets in the environment (or an `.env` created by your secrets
   manager — never committed).
3. Bring up the hardened stack (command above).
4. **Terminate TLS at a reverse proxy** (nginx / Caddy / an ALB) in front of
   `frontend` (:3000) and `backend` (:8000); set `HSTS_ENABLED=1`. Only the proxy
   is internet-facing; the datastores stay on the internal Docker network.
5. **First run — build the index:**
   ```bash
   curl -X POST https://api.example.com/ingest/fda -H "X-API-Key: $API_KEY"
   ```
   (or trigger the Airflow DAG). Verify: `GET /health` → `store.documents > 0`,
   and `GET /metrics` for live counters.

## Kubernetes path (sketch)

Each service maps to a Deployment + Service; datastores use StatefulSets +
PersistentVolumeClaims. Secrets come from a `Secret` (synced by External Secrets
Operator from your manager). Minimal backend shape:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: maistorage-backend }
spec:
  replicas: 2
  selector: { matchLabels: { app: backend } }
  template:
    metadata: { labels: { app: backend } }
    spec:
      containers:
        - name: backend
          image: REGISTRY/maistorage-backend:TAG
          ports: [{ containerPort: 8000 }]
          envFrom: [{ secretRef: { name: maistorage-secrets } }]
          env: [{ name: AUTH_ENABLED, value: "1" }, { name: JSON_LOGS, value: "1" }]
          resources:
            limits: { memory: 2Gi, cpu: "2" }
          readinessProbe: { httpGet: { path: /health, port: 8000 }, initialDelaySeconds: 40 }
          livenessProbe:  { httpGet: { path: /health, port: 8000 }, periodSeconds: 30 }
---
apiVersion: v1
kind: Service
metadata: { name: backend }
spec: { selector: { app: backend }, ports: [{ port: 8000, targetPort: 8000 }] }
```

Add an Ingress (TLS) → `frontend`/`backend`, a `HorizontalPodAutoscaler` on the
backend, a `ServiceMonitor` scraping `/metrics`, and a `NetworkPolicy` that keeps
Postgres/OpenSearch/Redis reachable only from `backend`. A Helm chart would
template the image tag, replica counts, resource limits, and the env/secret refs.

## Rollback

Immutable image tags make rollback a redeploy of the previous tag. The Postgres
schema migrations are additive (e.g. `sessions.owner`), so an older image reads a
newer DB safely.
