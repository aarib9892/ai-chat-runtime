# AI Chat Runtime

AI Chat Runtime is a full-stack chat application with persisted conversations and streamed assistant responses. The React client creates or restores a conversation, sends prompts to the FastAPI service, and renders each response as it arrives. The backend stores conversations and messages in PostgreSQL and streams output from the OpenAI Responses API.

## Features

- Creates, restores, and lists PostgreSQL-backed conversations.
- Persists user messages and assistant response state (`streaming`, `completed`, `stopped`, or `error`).
- Sends recent completed messages as context for each generation.
- Streams response events to the browser as newline-delimited JSON (NDJSON).
- Lets the user stop an in-progress stream from the client.

## Project layout

```text
ai-chat-runtime/
├── backend/
│   ├── app/                 # FastAPI application and uv project
│   └── migrations/          # PostgreSQL schema
└── frontend/
    └── react-frontend/      # Vite + React client
```

## Prerequisites

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/)
- Node.js 20 or later and npm
- PostgreSQL
- An OpenAI API key

## Run locally

1. Create the backend environment file from the example:

   ```bash
   cp backend/.env.example backend/.env
   ```

   Set `DATABASE_URL` to a PostgreSQL connection string and `OPENAI_API_KEY` to a valid API key. The local `.env` file is intentionally ignored by Git.

2. Create the database and apply the schema. Adjust the connection string for your PostgreSQL installation if needed:

   ```bash
   createdb ai_chat_runtime
   psql "postgresql://postgres:postgres@localhost:5432/ai_chat_runtime" \
     -f backend/migrations/001_initial_schema.sql
   ```

3. Start the backend from the repository root:

   ```bash
   cd backend
   uv run --project app --with asyncpg --with openai \
     fastapi dev app/main.py
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

`backend/app/pyproject.toml` currently declares FastAPI. The application source also imports `asyncpg` and `openai`, so the startup command installs those two packages for the run without altering the project files. Python-dotenv is provided through the existing `fastapi[standard]` dependency.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | PostgreSQL connection string used to create the application pool. |
| `OPENAI_API_KEY` | Yes | API key used by the OpenAI client. |

## API

All API routes are prefixed with `/api`.

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/conversations` | Create a conversation; accepts an optional `title`. |
| `GET` | `/conversations` | List up to 50 conversations, newest activity first. |
| `GET` | `/conversations/{conversation_id}` | Retrieve a conversation and its messages. |
| `POST` | `/conversations/{conversation_id}/messages` | Add a persisted user or assistant message. |
| `POST` | `/conversations/{conversation_id}/ask` | Save a user prompt and stream the assistant response as NDJSON. |

The streaming route emits `delta` events while text arrives, then a `done` event. If generation fails, it emits an `error` event.

## Development commands

Run these from `frontend/react-frontend`:

```bash
npm run lint
npm run build
```

## Git hygiene

Environment files are ignored in both application directories. Backend virtual environments, Python cache files, frontend dependencies, and build output are also excluded from version control. Use `backend/.env.example` as the safe starting point for local backend configuration; never commit credentials.
