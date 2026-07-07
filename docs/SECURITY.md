# Security

Production security posture for the FDA Drug-Info RAG (the `security-hardening`
pass, 2026-07-07). Every control below has a test that **proves the attack is
blocked**; the whole set runs offline in CI. Nothing here is theater.

Run the security suite:

```bash
cd backend && HF_HUB_OFFLINE=1 python -m pytest tests/test_security_*.py -q
```

---

## Threat model

**Exposed endpoints:** `/chat`, `/ask-agentic`, `/ingest[/fda[/grow]]`,
`/trace/{id}`, `/sessions`, `/sessions/{id}/messages`, `/health`.

**Untrusted inputs:** user questions (→ LLM + Postgres + rendered in the Next.js
UI), openFDA label content (→ index + agent context), Telegram messages (→ same
backend), and the `session_id` / `trace_id` path params.

**High-value assets:** the OpenAI key (cost/theft), Postgres chat data, the LLM
itself (cost abuse), and index integrity.

**Adversaries:** an anonymous internet abuser (cost-drain / DoS), a curious user
(IDOR — reading another user's session/trace), an injection attacker
(prompt-injection / XSS / SQLi), and a secrets thief.

---

## Controls (each with its proving test)

| # | Control | Where | Test |
|---|---|---|---|
| 1 | **API-key auth** (`X-API-Key`, `AUTH_ENABLED`) on `/chat`, `/ask-agentic`, `/ingest*`, `/sessions`, `/trace`; `/health` public | `app/security.py`, `app/main.py` | `test_security_auth.py` (unauth→401, bad key→401, valid passes, /health public) |
| 1 | **Rate limiting** per-caller + per-IP (fixed window; Redis or memory), LLM 20/min · ingest 5/min · default 120/min → 429 + Retry-After | `app/security.py` | `test_security_auth.py::test_rate_limit_returns_429` |
| 2 | **Unguessable ids**: `session_id`/`trace_id` are uuid4 (128-bit), never sequential | `app/db.py`, `app/agent/graph.py` | `test_security_idor.py::test_session_id_is_unguessable_uuid4` |
| 2 | **IDOR defense**: strict id-shape check before lookup; resources bound to the caller (`owner`); non-owned/unknown/malformed → **404** (no enumeration) | `app/api/sessions.py`, `app/api/trace.py`, `app/security.py` | `test_security_idor.py` (Bob can't read Alice's session/trace; malformed→404) |
| 3 | **Input validation**: empty/oversized question → 422; `session_id` length bound | `app/models.py` | `test_security_input.py` |
| 3 | **Body-size cap** (`MAX_BODY_BYTES`) → 413 before the body is read | `app/main.py` | `test_security_input.py::test_oversized_body_rejected_413` |
| 3 | **Parameterized SQL** everywhere (SQLAlchemy Core/ORM; no f-string SQL) | `app/db.py` | `test_security_input.py::test_sql_injection_payload_is_stored_as_data` |
| 4 | **XSS-safe output**: no `dangerouslySetInnerHTML`; all untrusted text (answers, citations, openFDA text) renders as escaped React text | `frontend/components/*` | `frontend/e2e/chat.spec.ts` (`<img onerror>`/`<script>` renders inert) |
| 4 | **Security headers + CSP** on the Next.js app *and* the FastAPI API (nosniff, `X-Frame-Options: DENY`/`frame-ancestors 'none'`, Referrer-Policy, Permissions-Policy, CSP without `unsafe-eval`; HSTS in prod) | `frontend/next.config.js`, `app/main.py` | `test_security_headers.py` |
| 5 | **Prompt-injection hardening**: guardrail (first node) blocks instruction-override / system-prompt-reveal / key-exfiltration / jailbreak, with drug-domain false-positive guards; loop capped at 3; retrieved content composed as inert DATA after the system instructions; no eval/exec path | `app/agent/nodes.py`, `app/agent/prompts.py` | `test_security_injection.py` |
| 6 | **Secrets**: env-only, `.env` gitignored, `.env.example` has placeholders only; no secrets in logs, `/health`, or error responses | `.env.example`, `app/api/health.py` | `test_security_hardening.py::test_health_has_no_internal_error_strings` |
| 7 | **CORS allowlist** (explicit origins, never `*` with credentials) | `app/main.py` | `test_security_hardening.py::test_cors_allowlist_only` |
| 7 | **Datastores internal-only** in prod (no published ports); Redis password; loopback binding in dev | `docker-compose.yml`, `docker-compose.prod.yml` | `docker compose … config` (postgres/opensearch/redis → no ports) |
| 7 | **Telegram** presents `X-API-Key` to the backend and runs the same guardrail; webhook-secret env for webhook mode | `app/services/telegram/handlers.py` | `test_security_hardening.py::test_telegram_presents_api_key_when_configured` |
| 8 | **No internal detail in responses**: request-id middleware + catch-all → generic 500; ask/ingest/health scrubbed of `str(e)` | `app/main.py`, `app/api/*` | `test_security_hardening.py::test_request_id_on_every_response` |
| 8 | **Outbound timeouts / graceful degradation**: openFDA (30 s) + provider calls time-bounded; every agent node degrades instead of crashing | `app/ingestion/openfda.py`, `app/agent/nodes.py` | `test_resilience.py` (existing) |
| 9 | **Non-root containers** + healthcheck + restart policy | `backend/Dockerfile`, `frontend/Dockerfile` | build/inspect |
| 9 | **Dependency scanning in CI** (pip-audit + npm audit fail the build) | `.github/workflows/security.yml` | CI |

---

## Access-control model

There is no per-user login yet; the **API key is the identity**. A stable,
non-reversible id (`k_<sha256(key)[:16]>`) is derived from the presented key and
recorded as the `owner` of any session or trace created during the request (via a
request-scoped contextvar). Reads are allowed only when the caller's id matches
the resource's owner. With `AUTH_ENABLED=0` (local dev) everything is `anon` and
ownership is not enforced. Non-owned, unknown, and malformed ids are all `404` so
an attacker cannot distinguish them (no enumeration oracle).

## Secrets & the production contract

All secrets come from the environment only — `OPENAI_API_KEY`, `DATABASE_URL`
creds, `API_KEYS`, `BACKEND_API_KEY`, `REDIS_PASSWORD`, `TELEGRAM__BOT_TOKEN`,
`TELEGRAM_WEBHOOK_SECRET`, `LANGFUSE_*`. `.env` is gitignored; `.env.example`
carries placeholders only. In production, inject them from a secrets manager
(**AWS Secrets Manager**, **Doppler**, or **HashiCorp Vault**) into the container
environment at deploy time — never bake them into an image layer or commit them.
Rotate `API_KEYS` by adding the new key to the comma-separated list, rolling
clients, then removing the old one. Secrets are never logged (errors log the
exception type/message server-side, not credentials) and never returned by
`/health` or error responses.

## Transport / deployment

Terminate **TLS at a reverse proxy** (nginx / Caddy / an ALB) in front of
`frontend` and `backend`; set `HSTS_ENABLED=1` there. Bring up the hardened stack
with:

```bash
docker compose -f docker-compose.yml -f docker-compose.redis.yml \
               -f docker-compose.prod.yml up --build -d
```

which enables auth + rate limiting + HSTS, keeps Postgres/OpenSearch/Redis off
the network, and sets a Redis password. OpenSearch runs with the security plugin
disabled for the demo; a real deployment should enable it (or keep 9200 strictly
on the internal network) and set OpenSearch credentials.

## Mobile roadmap (out of scope here)

This task is the web app + Python backend. A future mobile client (React
Native / Flutter — the developer's mobile stack) must use the same API-key auth
but **never embed the secret in the shipped app**: route through a
token-exchange / backend-for-frontend proxy that holds the key server-side and
issues short-lived per-device tokens.

## Responsible disclosure & known limitations

- **Disclosure:** report suspected vulnerabilities privately to the maintainer;
  do not open a public issue with exploit details. We aim to acknowledge within a
  few days and fix high-severity issues promptly.
- **Known limitations (by design, documented not hidden):**
  - Identity is an API key, not a per-user account; a leaked key impersonates its
    owner until rotated. A full auth system (OIDC/JWT) is the next step.
  - The trace store is in-process memory (fine for a single instance; use a
    shared store with the same ownership checks when scaling horizontally).
  - Prompt-injection defense is defense-in-depth (guardrail + data/instruction
    separation + no side-effects from model text), not a guarantee that a
    sufficiently novel jailbreak can never elicit an off-topic sentence — but it
    can never trigger a side effect, read another user's data, or exfiltrate a
    secret, because the model has no tools and secrets aren't in its context.
  - Rate limiting is a fixed window (simple, Redis-shared); a token-bucket/sliding
    window would smooth bursts further.
