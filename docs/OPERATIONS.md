# Operations

Running MaiStorage in production: logging, metrics, alerting, and the secrets
contract. Pairs with `docs/DEPLOYMENT.md` (how to ship it) and `docs/SECURITY.md`
(the controls).

## Structured logging

Set `JSON_LOGS=1` (the prod compose does) and every log line is one JSON object:

```json
{"ts":"2026-07-07T10:15:03+0000","level":"INFO","logger":"app.main","msg":"request",
 "request_id":"9f2ab1c0d3e4f5a6","method":"POST","path":"/chat","status":200,"latency_ms":842.5}
```

- Every request emits an access line with `request_id`, `method`, `path`,
  `status`, `latency_ms`. The same `request_id` is returned to the client as the
  `X-Request-ID` header and included in any 500 body — so a user-reported error
  maps to exact server logs.
- Unhandled errors log the exception server-side (`level":"ERROR","exc":...`) and
  return only a generic message — **no stack trace or secret ever reaches the
  client** (see SECURITY.md). The request body is never logged.
- Ship stdout to your log aggregator (CloudWatch, Loki, Datadog). `JSON_LOGS=0`
  (default) gives readable plain logs for local dev.

## Metrics — `GET /metrics`

Public, Prometheus text format, non-sensitive aggregates only (no PII, no
secrets). **Restrict it to the internal network / scraper in production** (it's
left public for demo scraping). Exposed series:

| Metric | Type | Meaning |
|---|---|---|
| `maistorage_requests_total{path,status}` | counter | requests by path class + HTTP status |
| `maistorage_request_latency_ms{path,quantile}` | gauge | p50 / p95 latency per path class |
| `maistorage_answers_total` / `_refusals_total` / `_blocked_total` | counter | agent outcomes |
| `maistorage_cache_hit_ratio{cache}` | gauge | retrieval + answer cache hit ratios |

`/health` remains the liveness/readiness probe (status + store doc count + cache
backend). Langfuse remains the per-request **tracing** backend (node spans, chunk
ids, token/cost/latency) — complementary to these aggregate metrics.

## Alerting (thresholds + hook design)

Wire these as Prometheus alerting rules (or your provider's monitors). The
alerter itself is a documented hook — the signals and thresholds are the design:

| Alert | Signal | Suggested threshold | Likely cause → action |
|---|---|---|---|
| **Error-rate spike** | `rate(maistorage_requests_total{status=~"5.."}[5m]) / rate(maistorage_requests_total[5m])` | > 2% for 5 min | dependency down (OpenAI/OpenSearch/DB) → check `/health`, provider status |
| **Latency spike** | `maistorage_request_latency_ms{path="chat",quantile="0.95"}` | > 20 s for 10 min | slow LLM / cold cache / retrieval degraded → check provider, cache hit ratio |
| **Cost spike** | Langfuse token/cost per window (traced) | > 2× 7-day baseline | abuse / a runaway loop → verify rate limits, inspect top callers |
| **Refusal-rate anomaly** | `maistorage_refusals_total` rate vs baseline | > 40% of answered turns | corpus gap / retrieval regression / injection probing → inspect traces |
| **Auth abuse** | 401/429 rate (`status="401"`/`"429"`) | sustained burst from one IP | credential stuffing / scraping → block IP, rotate keys |

A minimal hook: a sidecar scrapes `/metrics`, evaluates the rules, and posts to a
webhook (Slack/PagerDuty). We ship the metrics + thresholds; the notifier is a
few lines of glue per environment.

## Secrets — the production env-var contract

All secrets come from the environment only (`config.py` reads env; `.env` is
gitignored; `.env.example` has placeholders). **Inject them at deploy time from a
secrets manager** — AWS Secrets Manager, Doppler, or HashiCorp Vault — never bake
them into an image or commit them.

| Env var | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | LLM generation + embeddings |
| `API_KEYS` | prod (`AUTH_ENABLED=1`) | comma-separated accepted `X-API-Key` values |
| `BACKEND_API_KEY` | if Telegram + auth | key the bot presents to the backend |
| `DATABASE_URL` | yes (prod: Postgres) | e.g. `postgresql+psycopg://user:pass@host/db` |
| `REDIS_PASSWORD` / `REDIS_URL` | prod | shared cache + rate-limit store |
| `TELEGRAM__BOT_TOKEN` | if Telegram | BotFather token |
| `TELEGRAM_WEBHOOK_SECRET` | if webhook mode | verifies Telegram webhook source |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | optional | tracing |
| `OPENFDA_API_KEY` | optional | raises openFDA rate limits |

Operational toggles (non-secret): `AUTH_ENABLED`, `RATE_LIMIT_ENABLED`,
`RATE_LIMIT_*_PER_MIN`, `CORS_ORIGINS`, `HSTS_ENABLED`, `JSON_LOGS`,
`MAX_QUESTION_CHARS`, `MAX_BODY_BYTES`, `EMBED_MODEL`, `EMBED_DIM`, `OPENSEARCH_URL`.

**Rotation:** add the new key to `API_KEYS`, roll clients, then drop the old key —
zero downtime. Secrets are never returned by `/health`, `/metrics`, or error
responses, and never logged.
