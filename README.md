# AI Chat Runtime

AI Chat Runtime is a full-stack chat application with persisted conversations and streamed assistant responses. The React client creates or restores a conversation, sends prompts to the FastAPI service, and renders each response as it arrives. The backend stores conversations and messages in PostgreSQL and streams output from the OpenAI Responses API.

## Features

- Creates, restores, and lists PostgreSQL-backed conversations.
- Stores source documents, creates token-overlapped chunks, and supports vector similarity search.
- Uses selected document chunks as grounded reference material and displays their sources with assistant responses.
- Returns a clear fallback when the selected document does not contain sufficiently relevant evidence.
- Persists user messages and assistant response state (`streaming`, `completed`, `stopped`, or `error`).
- Sends recent completed messages as context for each generation.
- Streams response events to the browser as newline-delimited JSON (NDJSON).
- Lets the user stop an in-progress stream from the client.

## Project layout

```text
ai-chat-runtime/
├── docker-compose.yml       # Production-style local deployment
├── backend/
│   ├── app/                 # FastAPI application
│   ├── pyproject.toml       # Backend dependency manifest
│   └── migrations/          # PostgreSQL schema
└── frontend/
    └── react-frontend/      # Vite + React client
```

## Prerequisites

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/)
- Node.js 20 or later and npm
- PostgreSQL
- An OpenAI API key
- Docker and Docker Compose (optional, for the container deployment)

## Run locally

1. Create the backend environment file from the example:

   ```bash
   cp backend/.env.example backend/.env
   ```

   Set `DATABASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. The local `.env` file is intentionally ignored by Git.

2. Create the database and apply all migrations in order. Adjust the connection string for your PostgreSQL installation if needed:

   ```bash
   createdb ai_chat_runtime
   for migration in backend/migrations/*.sql; do
     psql "postgresql://postgres:postgres@localhost:5432/ai_chat_runtime" \
       -f "$migration"
   done
   ```

   For an existing database, apply only the migrations that have not already been run.

3. Start the backend from the repository root:

   ```bash
   cd backend
   uv run fastapi dev app/main.py
   ```

   The API starts on <http://127.0.0.1:8000>.

4. In a second terminal, start the frontend:

   ```bash
   cd frontend/react-frontend
   npm ci
   npm run dev
   ```

   Open the Vite URL shown in the terminal, normally <http://127.0.0.1:5173>.

### Backend dependency note

`backend/pyproject.toml` declares all backend runtime dependencies, including the OpenAI client, PostgreSQL driver, and settings validation.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | PostgreSQL connection string used to create the application pool. |
| `OPENAI_API_KEY` | Yes | API key used by the OpenAI client. |
| `OPENAI_MODEL` | Yes | Supported Responses API model used for chat and summaries. |

## Run with Docker Compose

1. Create a local root environment file from the safe template:

   ```bash
   cp .env.example .env
   ```

2. Set `POSTGRES_PASSWORD` and `OPENAI_API_KEY` in the ignored `.env` file. Do not commit that file.

3. Build and start the stack:

   ```bash
   docker compose up --build
   ```

The frontend is available at <http://localhost:3000>; it proxies `/api/` to the backend. The Compose migration service runs before the backend starts. For configuration, readiness, and existing-database guidance, see [container deployment](docs/container-deployment.md).

## API

All API routes are prefixed with `/api`.

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/conversations` | Create a conversation; accepts an optional `title`. |
| `GET` | `/conversations` | List up to 50 conversations, newest activity first. |
| `GET` | `/conversations/{conversation_id}` | Retrieve a conversation and its messages. |
| `POST` | `/conversations/{conversation_id}/messages` | Add a persisted user or assistant message. |
| `POST` | `/conversations/{conversation_id}/ask` | Save a user prompt and stream the assistant response as NDJSON; accepts an optional `document_id` for grounded retrieval. |
| `POST` | `/documents` | Store a document’s filename, content, and optional MIME type. |
| `POST` | `/documents/{document_id}/chunks` | Replace a document’s chunks using a token-overlapped split. |
| `POST` | `/documents/{document_id}/embeddings` | Generate and persist embeddings for all document chunks. |
| `POST` | `/documents/search` | Return the most similar embedded chunks for a search query. |

The streaming route emits `delta` events while text arrives, then a `done` event. If generation fails, it emits an `error` event.

## Development commands

Run these from `frontend/react-frontend`:

```bash
npm run lint
npm run build
```

## Git hygiene

Environment files are ignored at the repository root and in application directories. Backend virtual environments, Python cache files, frontend dependencies, and build output are also excluded from version control. Use `.env.example` or `backend/.env.example` as safe starting points; never commit credentials.
