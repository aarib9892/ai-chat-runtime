# AI Chat Runtime — Operations Guide

This document describes how to configure, run, inspect, test, and troubleshoot `ai-chat-runtime`.

It focuses on day-to-day development and production-like local operation.

---

## 1. Repository Layout

Expected structure:

```text
ai-chat-runtime/
│
├── README.md
├── docker-compose.yml
├── .env
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── app/
│   ├── migrations/
│   └── tests/
│
├── frontend/
│   └── react-frontend/
│       ├── Dockerfile
│       ├── nginx.conf
│       └── src/
│
└── docs/
    ├── architecture.md
    └── operations.md
```

---

## 2. Required Tooling

Local development expects:

```text
Python 3.12
uv
Node.js
npm
Docker
Docker Compose
PostgreSQL client tools (optional)
```

The Dockerized application does not require local PostgreSQL.

---

## 3. Environment Configuration

Configuration is managed through `pydantic-settings`.

The root `.env` is used by Docker Compose.

A typical example:

```env
POSTGRES_DB=ai_chat_runtime
POSTGRES_USER=ai_chat
POSTGRES_PASSWORD=change_me

OPENAI_API_KEY=replace_me
OPENAI_MODEL=replace_me

ENVIRONMENT=production
LOG_LEVEL=INFO

CORS_ORIGINS=http://localhost:3000

MAX_OUTPUT_TOKENS=2000
APP_MAX_INPUT_TOKENS=8000
SAFETY_MARGIN_TOKENS=500
TOKEN_ESTIMATION_BUFFER=0.05
SUMMARY_MAX_OUTPUT_TOKENS=800

EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

MAX_AGENT_STEPS=5
MAX_AGENT_TOOL_CALLS=8
MAX_IDENTICAL_TOOL_CALLS=2

MAX_CONCURRENT_AGENT_RUNS=5
AGENT_QUEUE_TIMEOUT_SECONDS=5

ASK_RATE_LIMIT=20
ASK_RATE_WINDOW_SECONDS=60

OPENAI_INPUT_COST_PER_1M_USD=0
OPENAI_OUTPUT_COST_PER_1M_USD=0
```

Do not commit `.env`.

Commit `.env.example` with placeholders.

---

## 4. Secret Hygiene

The following must never be committed:

```text
OPENAI_API_KEY
database passwords
authorization tokens
cookies
private connection strings
```

Check tracked environment files:

```bash
git ls-files | grep -E '(^|/)\.env'
```

Ideally only `.env.example` appears.

Search for accidentally committed API keys:

```bash
git grep -n "sk-"
```

If a real key has ever been committed or shared publicly, rotate it.

---

## 5. Local Backend Development

From:

```text
backend/
```

install dependencies:

```bash
uv sync
```

Run the backend:

```bash
uv run uvicorn app.main:app --reload
```

Or use your FastAPI dev command if configured.

The backend normally runs on:

```text
http://127.0.0.1:8000
```

---

## 6. Local Frontend Development

From:

```text
frontend/react-frontend/
```

install dependencies:

```bash
npm install
```

Run Vite:

```bash
npm run dev
```

The frontend normally runs on:

```text
http://localhost:5173
```

During local development, ensure CORS includes this origin.

---

## 7. Docker Build

From the repository root:

```bash
docker compose build
```

Expected images:

```text
ai-chat-runtime-backend
ai-chat-runtime-migrate
ai-chat-runtime-frontend
```

If the frontend build fails, Docker may be surfacing TypeScript compile errors that the development server did not block on.

Test locally with:

```bash
cd frontend/react-frontend
npm run build
```

---

## 8. Start the Docker Stack

From the repository root:

```bash
docker compose up
```

Or detached:

```bash
docker compose up -d
```

Expected startup order:

```text
db
  ↓ healthy
migrate
  ↓ exits 0
backend
  ↓ running
frontend
  ↓ running
```

---

## 9. Check Container State

Run:

```bash
docker compose ps
```

For all services, including completed one-shot jobs:

```bash
docker compose ps -a
```

Expected conceptual state:

```text
db         Up (healthy)
migrate    Exited (0)
backend    Up
frontend   Up
```

`migrate` exiting with code `0` is correct.

---

## 10. Application URL

The Dockerized application is available at:

```text
http://localhost:3000
```

The browser only talks to Nginx.

Nginx serves the React application and proxies `/api/*` to FastAPI.

---

## 11. Health Checks

Frontend-proxied backend readiness:

```bash
curl -i http://localhost:3000/health/backend
```

Expected:

```json
{ "status": "ready" }
```

Backend health endpoints:

```text
/health/live
/health/ready
```

Meaning:

```text
live  → process is running
ready → database is reachable
```

---

## 12. Docker Logs

Follow all service logs:

```bash
docker compose logs -f
```

Backend only:

```bash
docker compose logs -f backend
```

Migration logs:

```bash
docker compose logs migrate
```

Database logs:

```bash
docker compose logs -f db
```

Frontend/Nginx:

```bash
docker compose logs -f frontend
```

Limit output:

```bash
docker compose logs backend --tail=100
```

---

## 13. Request Tracing

Every request receives an `x-request-id`.

Example:

```text
x-request-id: 7b533cbc-...
```

Use this value to correlate:

```text
HTTP request
        ↓
FastAPI logs
        ↓
agent steps
        ↓
tool activity
        ↓
completion/failure
```

Structured logs include the same request ID.

---

## 14. Database Access

Open a PostgreSQL shell inside Docker:

```bash
docker compose exec db \
  psql \
  -U ai_chat \
  -d ai_chat_runtime
```

Adjust values if your `.env` uses different names.

Useful commands:

```sql
\dt
```

List migrations:

```sql
SELECT *
FROM schema_migrations
ORDER BY applied_at;
```

Exit:

```sql
\q
```

---

## 15. Database Migrations

Migrations live under:

```text
backend/migrations/
```

The migration runner executes pending SQL files in filename order.

Applied migrations are tracked in:

```text
schema_migrations
```

The migration service runs automatically before the backend starts.

---

## 16. Fresh Database Bootstrap

To verify full reproducibility:

```bash
docker compose down -v
docker compose up --build
```

Warning:

```text
-v
```

deletes the PostgreSQL volume.

Use this only when you intentionally want a fresh database.

A successful clean bootstrap proves:

```text
schema
migrations
backend
frontend
```

can start without manual database setup.

---

## 17. Stop Without Deleting Data

Use:

```bash
docker compose down
```

This keeps the PostgreSQL volume.

Restart with:

```bash
docker compose up -d
```

Existing conversations and persisted data should remain.

---

## 18. Delete Local Docker Database

Use:

```bash
docker compose down -v
```

This removes:

```text
postgres_data
```

and therefore deletes local Docker database state.

Do not use `-v` when you want to preserve conversations or RAG documents.

---

## 19. Deterministic Tests

From:

```text
backend/
```

run:

```bash
uv run pytest -v
```

The current deterministic suite covers:

```text
settings validation
environment normalization
CORS parsing
rate limiting
per-client limiter behavior
token budgeting
tool result serialization
tool error serialization
provider error mapping
```

Current baseline:

```text
18/18 PASS
```

---

## 20. RAG Evaluation

Run:

```bash
uv run python -m app.evals.rag_eval \
  --document-id <evaluation-document-id>
```

The fixture document must:

- exist
- have chunks
- have embeddings
- use the configured embedding model

Current evaluation checks:

```text
Hit@1
Hit@3
negative-query rejection
```

Current known-good baseline:

```text
Hit@1:               6/6
Hit@3:               6/6
Negative rejection:  6/6
Overall:             12/12 PASS
```

---

## 21. Agent Evaluation

Run:

```bash
uv run python -m app.evals.agent_eval
```

The suite covers:

```text
multi-step tool execution
single-tool execution
no-tool completion
tool failure recovery
max-step safeguard
max-tool safeguard
repeated-tool safeguard
```

Current baseline:

```text
7/7 PASS
```

---

## 22. Combined AI Evaluation

Run:

```bash
uv run python -m app.evals.run_all \
  --document-id <evaluation-document-id>
```

Expected ending:

```text
RAG:   PASS
Agent: PASS

All AI evals passed.
```

---

## 23. API Smoke Test

With Docker running:

```bash
uv run python -m app.evals.api_smoke
```

The smoke test checks:

```text
Nginx routing
backend readiness
conversation creation
request ID propagation
NDJSON streaming
assistant completion
database persistence
conversation reload
```

Expected ending:

```text
API SMOKE: PASS
```

---

## 24. Final Quality Gate

Run:

```bash
uv run python -m app.evals.quality_gate \
  --document-id <evaluation-document-id>
```

This combines:

```text
pytest
RAG eval
agent eval
API smoke
```

Expected result:

```text
Tests: PASS
RAG:   PASS
Agent: PASS
API:   PASS

QUALITY GATE: PASS
```

---

## 25. Common Failure: Missing Runtime Dependency

Example:

```text
ModuleNotFoundError: No module named 'asyncpg'
```

or:

```text
ModuleNotFoundError: No module named 'openai'
```

Do not patch the Dockerfile with ad-hoc `pip install`.

Add the dependency properly:

```bash
cd backend
uv add asyncpg
```

or:

```bash
uv add openai
```

Then rebuild:

```bash
cd ..
docker compose build backend migrate
```

The intended dependency path is:

```text
pyproject.toml
    ↓
uv.lock
    ↓
uv sync --frozen
    ↓
Docker image
```

---

## 26. Common Failure: Docker Build Context Path

If Compose reports:

```text
.../backend/backend not found
```

you are likely running with a Compose file whose build context assumes repository-root execution.

Run Compose from:

```text
~/ai-chat-runtime
```

and keep:

```yaml
build:
  context: ./backend
```

for backend services.

---

## 27. Common Failure: Missing Compose Variables

Symptoms:

```text
POSTGRES_DB variable is not set
POSTGRES_USER variable is not set
POSTGRES_PASSWORD variable is not set
```

Make sure the repository-root `.env` exists.

Prefer required-variable syntax in Compose:

```yaml
POSTGRES_DB: ${POSTGRES_DB:?POSTGRES_DB is required}
```

This is safer than silently defaulting to blank strings.

---

## 28. Common Failure: Backend Restart Loop

Check:

```bash
docker compose ps -a
```

Then inspect:

```bash
docker compose logs backend --tail=100
```

Typical causes include:

```text
missing dependency
invalid settings
database unavailable
migration failure
import error
```

---

## 29. Common Failure: Migration Container Exited 1

Inspect:

```bash
docker compose logs migrate
```

Do not manually fix the database first.

A migration failure is usually evidence that the migration chain cannot reproduce the schema from a clean database.

Fix the migration scripts, then retry.

---

## 30. Common Failure: RAG Returns No Chunks

Check:

```sql
SELECT id, filename
FROM documents
WHERE id = '<document-id>';
```

Then:

```sql
SELECT
    COUNT(*) AS total_chunks,
    COUNT(embedding) AS embedded_chunks
FROM document_chunks
WHERE document_id = '<document-id>';
```

Then verify embedding model:

```sql
SELECT
    embedding_model,
    COUNT(*)
FROM document_chunks
WHERE document_id = '<document-id>'
GROUP BY embedding_model;
```

Common causes:

```text
wrong fixture UUID
document missing
no chunks
null embeddings
embedding-model mismatch
```

---

## 31. Common Failure: Frontend Build Fails

Run locally:

```bash
cd frontend/react-frontend
npm run build
```

Typical issues include:

```text
TypeScript errors
JSX stored in .ts instead of .tsx
incorrect React event types
stale imports
```

Fix the local production build first, then rebuild Docker.

---

## 32. Common Failure: Streaming Appears All At Once

Check Nginx configuration.

Streaming routes should disable buffering:

```nginx
proxy_buffering off;
proxy_cache off;
```

The frontend should receive NDJSON chunks incrementally.

---

## 33. Common Failure: Conversation Busy

A second simultaneous request for the same conversation can return:

```text
CONVERSATION_BUSY
```

This is expected behavior.

It protects the invariant that one conversation has at most one active assistant stream.

---

## 34. Common Failure: Server Busy

If the global agent semaphore is saturated and the queue timeout expires, the request can return:

```text
SERVER_BUSY
```

Relevant settings:

```text
MAX_CONCURRENT_AGENT_RUNS
AGENT_QUEUE_TIMEOUT_SECONDS
```

---

## 35. Common Failure: Rate Limited

Requests beyond the configured window may return:

```text
RATE_LIMITED
```

Relevant settings:

```text
ASK_RATE_LIMIT
ASK_RATE_WINDOW_SECONDS
```

The current limiter is process-local.

---

## 36. Common Failure: Mid-Stream Provider Error

Once streaming has started, HTTP status is already committed.

Provider errors therefore appear as NDJSON:

```json
{
  "type": "error",
  "code": "PROVIDER_TIMEOUT",
  "message": "The model provider timed out.",
  "retryable": true
}
```

The frontend should treat this as a terminal stream event.

---

## 37. Development vs Production

The settings layer supports:

```text
development
test
production
```

Typical behavior:

### development

- API docs enabled
- debug-friendly logging
- local frontend CORS

### production

- API docs disabled
- explicit production CORS
- INFO-level logging
- proxy trust configured at deployment

---

## 38. CORS

Local development:

```env
CORS_ORIGINS=http://localhost:5173
```

Dockerized frontend:

```env
CORS_ORIGINS=http://localhost:3000
```

Multiple origins can be comma-separated.

---

## 39. Proxy and Client IP

The application should not blindly trust:

```text
X-Forwarded-For
```

Production deployments should trust forwarding headers only from known reverse proxies.

Proxy-header configuration belongs at the ASGI server/deployment layer.

---

## 40. Production Proxy Notes

A production Uvicorn deployment may use:

```text
--proxy-headers
--forwarded-allow-ips=<trusted-proxy>
```

Do not trust all forwarding sources on an internet-exposed server.

---

## 41. Logging Policy

Application code should use structured logging instead of `print()`.

Eval scripts may use `print()` because they are CLI/reporting tools.

Search runtime code for debug prints:

```bash
grep -R "print(" backend/app \
  --exclude-dir=evals
```

Convert remaining runtime prints to structured logging.

---

## 42. Security Checklist

Before publishing or deploying:

```text
.env not tracked
API keys rotated if exposed
database credentials not committed
no sensitive prompt logging
no Authorization logging
CORS restricted
trusted proxy configured
debug endpoints disabled in production
```

Useful checks:

```bash
git status
git grep -n "sk-"
git ls-files | grep -E '(^|/)\.env'
```

---

## 43. Final Repository Check

Before marking a release:

```bash
git status
```

Verify expected files exist:

```text
README.md
.env.example
docker-compose.yml

docs/
├── architecture.md
└── operations.md

backend/
├── Dockerfile
├── migrations/
├── app/evals/
└── app/tests/

frontend/react-frontend/
├── Dockerfile
└── nginx.conf
```

---

## 44. Final Release Verification

Recommended final sequence:

```bash
docker compose up -d
```

Then:

```bash
cd backend
uv run pytest -q
```

Then:

```bash
uv run python -m app.evals.quality_gate \
  --document-id <evaluation-document-id>
```

Then:

```bash
cd ..
git status
```

The project is ready when the final quality gate passes and no unintended secrets or local files are tracked.
