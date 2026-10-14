# Container deployment

Docker Compose starts PostgreSQL with pgvector, applies backend migrations, runs the FastAPI service, and serves the React build through Nginx. The frontend is available at `http://localhost:3000`; Nginx proxies `/api/` to the backend and disables proxy buffering for NDJSON streams.

## Configure without committing secrets

Copy the root template and edit only the ignored copy:

```bash
cp .env.example .env
```

Set a strong `POSTGRES_PASSWORD` and a server-side `OPENAI_API_KEY`. The repository ignores `.env` and `.env.*` files while retaining the explicitly safe `.env.example` templates. Docker build contexts also exclude environment files.

Start the stack with:

```bash
docker compose up --build
```

The backend waits for the migration service to complete successfully. Its readiness endpoint is `GET /health/ready`; the frontend exposes it as `GET /health/backend`.

## Runtime configuration

The backend validates configuration at startup through `Settings`. `DATABASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are required. The Compose file exposes optional limits for output tokens, context budgeting, agent safety, request rate limits, concurrency, CORS, and usage-cost estimation.

The configured model must appear in `backend/app/config/model_capabilities.py`. The initial supported GPT-6 Astra, GPT-6.1 Sol, and GPT-6 Luna entries use their documented 1.05-million-token context windows; the application still applies its smaller configurable input budget.

Set `CORS_ORIGINS` to the deployed frontend origin when it is not `http://localhost:3000`.

## Migrations and existing databases

The Compose migrator stores applied filenames in `schema_migrations`, so it is safe to restart against a database it initialized. It is intended for a fresh database volume. For an existing database previously migrated with manual SQL files, first back it up and establish the migration ledger intentionally; otherwise the runner cannot infer which historical migrations have already been applied.

## Stop and reset

Stop the stack with `docker compose down`. PostgreSQL data is held in the named `postgres_data` volume. Remove that volume only when an intentional local data reset is required:

```bash
docker compose down --volumes
```
