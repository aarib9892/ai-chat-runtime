# AI Chat Runtime

`ai-chat-runtime` is a production-oriented LLM application runtime built from scratch using **React, FastAPI, PostgreSQL, pgvector, and the OpenAI Responses API**.

The project explores the infrastructure and runtime mechanics required to build reliable AI applications beyond a basic `prompt → model → response` integration.

Instead of relying on orchestration frameworks such as LangChain or LlamaIndex, the core runtime implements the important pieces directly:

- end-to-end token streaming
- persistent multi-turn conversations
- token-aware context construction
- rolling conversation summarization
- retrieval-augmented generation (RAG)
- vector search with PostgreSQL + pgvector
- tool/function calling
- multi-step agent execution
- agent loop safeguards
- structured streaming events
- request tracing and structured logging
- token, latency, and usage telemetry
- structured error handling
- concurrency protection
- rate limiting
- production configuration
- Dockerized deployment
- deterministic regression tests
- live RAG and agent evaluations
- end-to-end API smoke testing

The goal of the project is not simply to build a chat interface.

It is to understand and implement the **runtime architecture behind production AI systems**.

## Documentation

For deeper implementation details:

- [Architecture](docs/architecture.md)
- [Operations Guide](docs/operations.md)

---

## Why This Project Exists

Calling an LLM API is relatively simple:

```text
user prompt
    ↓
model
    ↓
response
```

A production AI application quickly becomes much more complicated.

The runtime must answer questions such as:

- How should model output be streamed through the backend to the browser?
- How should conversation state be persisted?
- How much conversation history should be sent back to the model?
- What happens when a conversation exceeds the application's context budget?
- How should older conversation history be summarized?
- How should external knowledge be retrieved and injected into model context?
- How should tool arguments be validated?
- What happens when a tool fails?
- How does the model continue after receiving a tool result?
- How can an agent perform multiple model/tool steps?
- What prevents an agent from entering an infinite tool loop?
- How should partial, stopped, incomplete, and failed responses be represented?
- How should model token usage and latency be measured?
- How should concurrent requests be controlled?
- How should provider failures be translated into application-level errors?
- How do we test behavior produced by a probabilistic model?

`ai-chat-runtime` was built incrementally to answer these questions directly.

---

## What Makes It Different From a Basic Chat App

A typical LLM chat application might look like:

```text
React
   ↓
API
   ↓
OpenAI
   ↓
response
```

This project instead implements a runtime with explicit layers for:

```text
conversation persistence
        ↓
context planning
        ↓
optional retrieval
        ↓
agent execution
        ↓
tool execution
        ↓
streaming
        ↓
telemetry
        ↓
persistent result
```

Each concern is implemented separately so that the behavior of the system remains visible and inspectable.

For example:

- RAG retrieval is implemented directly with embeddings and pgvector.
- Agent execution uses an explicit model/tool loop.
- Tool arguments are validated with Pydantic.
- Agent steps and tool calls are persisted separately.
- Context selection is controlled by an application token budget.
- Long conversations can be compressed into rolling summaries.
- Streaming uses structured NDJSON events.
- Rate limiting and concurrency protection are handled independently.
- AI behavior is evaluated separately from deterministic application logic.

---

# Architecture

At a high level, the production deployment looks like this:

```text
                         Browser
                            │
                            │ HTTP / NDJSON
                            ▼
                    ┌───────────────┐
                    │ React + Vite  │
                    │      UI       │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     Nginx     │
                    │               │
                    │ Static UI     │
                    │ /api proxy    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    FastAPI    │
                    │               │
                    │ Chat Runtime  │
                    └───────┬───────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
      Agent Runtime     RAG Runtime    PostgreSQL
             │              │           + pgvector
             │              │
             ▼              ▼
      OpenAI Responses   OpenAI
            API          Embeddings
```

The backend is organized into distinct layers:

```text
API / HTTP
    ↓
Application services
    ↓
Context / RAG / Agent runtimes
    ↓
Repositories
    ↓
PostgreSQL + pgvector
```

This separation keeps HTTP handling, model orchestration, persistence, retrieval, and tool execution independent from one another.

---

## Request Lifecycle

A typical `/ask` request follows roughly this path:

```text
POST /api/conversations/{id}/ask
              │
              ▼
        Rate limiting
              │
              ▼
   Conversation concurrency check
              │
              ▼
      Acquire agent slot
              │
              ▼
 Persist user + assistant placeholder
              │
              ▼
      Build context plan
              │
              ├───────────────┐
              │               │
              ▼               ▼
      recent messages    rolling summary
              │               │
              └───────┬───────┘
                      │
                      ▼
              Optional RAG
                      │
                      ▼
                Agent Runtime
                      │
             ┌────────┴────────┐
             │                 │
             ▼                 ▼
        final response      tool call
                               │
                               ▼
                         execute tool
                               │
                               ▼
                         tool observation
                               │
                               └──────→ next model step
                      │
                      ▼
                NDJSON stream
                      │
                      ▼
                  React UI
                      │
                      ▼
        Persist result + telemetry
```

The model generation itself is intentionally kept outside long-running database transactions.

Database transactions are instead used for short persistence operations and state transitions.

---

## Streaming Protocol

The application does not stream raw text directly.

The backend emits structured NDJSON events:

```json
{"type":"message_ids","user_message_id":"...","assistant_message_id":"..."}
{"type":"agent_step_started","step":1}
{"type":"response_id","response_id":"..."}
{"type":"delta","delta":"Hello"}
{"type":"delta","delta":" world"}
{"type":"agent_step_completed","step":1,"outcome":"final"}
{"type":"done"}
```

Other event types include:

```text
sources

tool_call
tool_result
tool_error

incomplete
error
```

This allows the frontend to distinguish between:

```text
model text
tool execution
agent progress
sources
completion
controlled termination
runtime failure
```

instead of treating the response as one unstructured text stream.

---

## Conversation Persistence

Conversations and messages are stored in PostgreSQL.

Assistant messages can exist in multiple lifecycle states:

```text
streaming
completed
stopped
error
incomplete
```

Only completed assistant messages participate in future model context.

Stopped, incomplete, and failed outputs remain persisted for history and debugging purposes.

---

## Context Management

The application does not blindly send the full conversation back to the model.

Instead, it calculates a context budget:

```text
model context window
        ↓
subtract output allowance
        ↓
subtract safety margin
        ↓
apply application input ceiling
        ↓
planning input budget
```

Recent messages are retained verbatim.

Older messages can be compressed into a rolling conversation summary.

This lets the application support long-running conversations while controlling:

- token usage
- latency
- model cost
- context-window pressure

---

## Retrieval-Augmented Generation

The RAG pipeline is implemented directly:

```text
Document
   ↓
token-based chunking
   ↓
embeddings
   ↓
PostgreSQL + pgvector
   ↓
cosine similarity search
   ↓
similarity threshold
   ↓
retrieved context
   ↓
model
```

Retrieved knowledge is injected into model context transiently rather than being stored as normal conversation messages.

Source attribution is persisted separately from conversation history.

This keeps:

```text
conversation memory
```

separate from:

```text
retrieved external knowledge
```

The retrieval layer supports:

- document-scoped retrieval
- top-K vector search
- cosine similarity ranking
- similarity thresholds
- negative-query rejection
- source persistence

---

## Tool Calling

The runtime exposes deterministic tools such as:

```text
calculate
get_text_length
```

Each tool has:

- an OpenAI tool schema
- a Pydantic argument model
- a handler
- runtime validation
- structured success/error output

Tool failures are treated as observations returned to the model rather than automatically terminating the agent.

Example:

```text
Model
  ↓
calculate(10 / 0)
  ↓
tool error
  ↓
error observation returned to model
  ↓
model explains the failure
```

This lets the agent recover from tool-level failures when possible.

---

## Agent Runtime

The agent runtime is implemented as an explicit loop:

```text
model step
    │
    ├── final answer
    │       ↓
    │    complete
    │
    └── tool call
            ↓
       validate arguments
            ↓
        execute tool
            ↓
       return observation
            ↓
       next model step
```

An **agent step** represents one model response or decision.

A **tool call** represents an action requested during that step.

These concepts are persisted separately so that agent execution can later be inspected and analyzed.

The runtime currently executes tools sequentially with:

```text
parallel_tool_calls = false
```

---

## Agent Safeguards

Multi-step agents can continue indefinitely if they repeatedly request tools or fail to reach a final answer.

The runtime therefore enforces:

```text
MAX_AGENT_STEPS
MAX_AGENT_TOOL_CALLS
MAX_IDENTICAL_TOOL_CALLS
```

Safeguard termination produces:

```text
incomplete
```

rather than:

```text
error
```

because the runtime itself behaved correctly and intentionally stopped further execution.

Examples include:

```text
max_agent_steps
max_tool_calls
repeated_tool_call
```

---

## Observability

Every request receives a request ID.

Structured JSON logs include metadata such as:

```text
request_id
conversation_id
message_id
assistant_message_id
agent step
tool name
duration_ms
input_tokens
output_tokens
total_tokens
status
```

Sensitive values such as:

```text
API keys
authorization headers
cookies
full prompts
model output text
retrieved chunk contents
arbitrary tool arguments
```

are not logged by default.

---

## Usage Telemetry

Agent-step telemetry includes:

```text
duration
input tokens
output tokens
total tokens
provider response ID
step outcome
```

Message-level usage aggregates:

```text
model
model calls
input tokens
output tokens
total tokens
duration
estimated cost
```

Provider pricing is configurable rather than hard-coded into business logic.

---

## Production Engineering

The runtime includes several protections beyond AI-specific functionality.

### Request Tracing

Every request receives a request ID which is propagated through structured logs and returned to the client.

### Concurrency Protection

The system uses:

- a PostgreSQL invariant preventing multiple active assistant streams for one conversation
- a global semaphore limiting concurrent agent runs
- a queue timeout when the server is saturated

### Rate Limiting

Requests are limited per client key.

The current implementation is process-local and would need a shared store such as Redis for horizontally scaled deployment.

### Error Taxonomy

Provider and application failures are translated into structured error codes such as:

```text
INVALID_REQUEST
CONVERSATION_NOT_FOUND

PROVIDER_RATE_LIMITED
PROVIDER_TIMEOUT
PROVIDER_UNAVAILABLE
PROVIDER_ERROR

DATABASE_ERROR
AGENT_RUNTIME_ERROR
INTERNAL_ERROR

CONVERSATION_BUSY
SERVER_BUSY
RATE_LIMITED
```

Errors that occur before streaming begins can use normal HTTP status codes.

Once response streaming has started, failures are represented using structured stream events.

Example:

```json
{
  "type": "error",
  "code": "PROVIDER_TIMEOUT",
  "message": "The model provider timed out.",
  "retryable": true
}
```

---

# Technology Stack

## Frontend

- React
- Vite
- TypeScript
- Fetch API
- ReadableStream
- AbortController

## Backend

- Python 3.12
- FastAPI
- Pydantic
- pydantic-settings
- asyncpg
- OpenAI Python SDK
- tiktoken

## Database

- PostgreSQL
- pgvector

## Infrastructure

- Docker
- Docker Compose
- Nginx
- uv

---

# Project Structure

```text
ai-chat-runtime/
│
├── README.md
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   │
│   ├── app/
│   │   ├── api/
│   │   ├── config/
│   │   ├── db/
│   │   ├── evals/
│   │   ├── middleware/
│   │   ├── observability/
│   │   ├── repositories/
│   │   ├── runtime/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── tools/
│   │
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
```

---

# Running With Docker

Create a root `.env` using `.env.example` as a reference.

Example:

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

MAX_AGENT_STEPS=5
MAX_AGENT_TOOL_CALLS=8
MAX_IDENTICAL_TOOL_CALLS=2

MAX_CONCURRENT_AGENT_RUNS=5
AGENT_QUEUE_TIMEOUT_SECONDS=5

ASK_RATE_LIMIT=20
ASK_RATE_WINDOW_SECONDS=60
```

Then build:

```bash
docker compose build
```

Start the application:

```bash
docker compose up
```

Or run in detached mode:

```bash
docker compose up -d
```

Open:

```text
http://localhost:3000
```

The startup flow is:

```text
PostgreSQL
    ↓
database healthy
    ↓
migration container
    ↓
migrations complete
    ↓
FastAPI
    ↓
Nginx / React
```

PostgreSQL is not exposed publicly by default.

---

## Database Migrations

SQL migrations live under:

```text
backend/migrations/
```

The migration runner records applied migrations in:

```text
schema_migrations
```

This allows a completely empty database to be bootstrapped without manually executing SQL.

The migration service runs once during startup and exits successfully after applying pending migrations.

---

## Health Checks

Liveness:

```text
/health/live
```

Readiness:

```text
/health/ready
```

Through the frontend Nginx proxy:

```text
/health/backend
```

Readiness verifies that the application can communicate with PostgreSQL.

---

# Testing

Deterministic application behavior is tested using `pytest`.

Run:

```bash
cd backend

uv run pytest -v
```

The regression suite currently covers:

- configuration validation
- environment normalization
- CORS parsing
- rate limiting
- per-client rate-limit isolation
- token budgeting
- tool result serialization
- tool error serialization
- provider timeout mapping
- provider connection-error mapping
- provider rate-limit mapping
- provider status-error mapping

Current deterministic suite:

```text
18/18 PASS
```

---

# AI Evaluation

Probabilistic AI behavior is tested separately from deterministic application logic.

---

## RAG Evaluation

The retrieval suite evaluates:

```text
Hit@1
Hit@3
negative-query rejection
```

Run:

```bash
uv run python -m app.evals.rag_eval   --document-id <evaluation-document-id>
```

Current evaluation result:

```text
Hit@1:               6/6
Hit@3:               6/6
Negative rejection:  6/6

Overall:             12/12 PASS
```

---

## Agent Evaluation

The agent suite covers:

- multi-step tool execution
- single-tool execution
- direct answers without tools
- tool failure recovery
- max-agent-step protection
- max-tool-call protection
- repeated-tool-call protection

Run:

```bash
uv run python -m app.evals.agent_eval
```

Current result:

```text
7/7 PASS
```

---

## Combined AI Evaluation

Run both RAG and agent evaluations:

```bash
uv run python -m app.evals.run_all   --document-id <evaluation-document-id>
```

Successful output ends with:

```text
RAG:   PASS
Agent: PASS

All AI evals passed.
```

---

# API Smoke Test

With the Docker stack running:

```bash
uv run python -m app.evals.api_smoke
```

The smoke test verifies:

```text
Nginx routing
FastAPI readiness
conversation creation
request tracing
NDJSON streaming
LLM completion
message persistence
conversation reload
```

Example successful result:

```text
PASS health check
PASS conversation creation
PASS request id
PASS streaming
PASS assistant response
PASS persistence reload

API SMOKE: PASS
```

---

# Final Quality Gate

The complete project quality gate combines:

```text
deterministic regression tests
        +
RAG retrieval eval
        +
agent runtime eval
        +
Docker/API smoke test
```

Run:

```bash
uv run python -m app.evals.quality_gate   --document-id <evaluation-document-id>
```

A successful run ends with:

```text
Tests: PASS
RAG:   PASS
Agent: PASS
API:   PASS

QUALITY GATE: PASS
```

The current quality gate covers:

```text
18 deterministic regression tests
12 RAG evaluation cases
7 agent evaluation cases
1 end-to-end Docker/API smoke flow
```

---

# Important Engineering Decisions

## No Heavy AI Orchestration Framework

The project intentionally implements context management, RAG, tool execution, and agent orchestration directly.

This makes the runtime behavior visible rather than hidden behind framework abstractions.

---

## Database Transactions Do Not Wrap Model Generation

External LLM calls may take several seconds.

Holding a database transaction open for the entire generation would unnecessarily retain connections and locks.

The application therefore uses short transactions for persistence and state transitions, while model generation happens outside those transactions.

---

## Tool Failures Are Observations

A failed tool call does not automatically mean the agent failed.

Instead:

```text
tool failure
    ↓
structured observation
    ↓
model
    ↓
recovery / explanation
```

This allows the model to reason about recoverable tool errors.

---

## Incomplete Is Different From Error

Safeguard termination is represented as:

```text
incomplete
```

Infrastructure and runtime failures are represented as:

```text
error
```

For example:

```text
max_agent_steps
```

means the runtime successfully enforced a safety limit.

It does not mean the server crashed.

---

## Telemetry Should Not Break Successful Responses

Observability is important, but it should not become a critical dependency for successful model output.

If usage telemetry persistence fails after a completed answer, the failure is logged rather than automatically converting the successful assistant result into a failed response.

---

# Known Limitations

The project intentionally keeps several areas simple:

- rate limiting is currently process-local
- agent tools execute sequentially
- `parallel_tool_calls` is disabled
- authentication is not implemented
- the RAG eval requires a known embedded evaluation fixture
- horizontally scaled deployment would require distributed rate limiting
- trusted proxy configuration must be set correctly in production
- the current tools are intentionally simple deterministic examples
- the project focuses on application/runtime engineering rather than model training

These are explicit architectural boundaries rather than hidden assumptions.

---

# Development Milestones

The project was built incrementally:

```text
M1  Basic LLM Request / Response
M2  End-to-End Streaming
M3  Conversation Context
M4  Persistence & Conversation Identity
M5  Token-Aware Context Management
M6  Retrieval-Augmented Generation
M7  Tool / Function Calling
M8  Agent Runtime
M9  Production Engineering
```

Each milestone builds on the previous runtime rather than replacing it with an abstraction framework.

---

# Current Runtime Flow

The application currently supports the complete path:

```text
user message
    ↓
persistent conversation
    ↓
token-aware context planning
    ↓
rolling summary when needed
    ↓
optional RAG retrieval
    ↓
multi-step agent runtime
    ↓
tool execution
    ↓
structured NDJSON streaming
    ↓
React UI
    ↓
usage + runtime telemetry
    ↓
persistent conversation reload
```

---

# Repository Goals

This repository is intended to demonstrate practical understanding of:

- LLM application architecture
- streaming protocols
- asynchronous backend systems
- context engineering
- RAG
- vector search
- agent runtimes
- tool execution
- failure handling
- observability
- evaluation
- concurrency
- production deployment

The emphasis is on understanding how the runtime works internally rather than relying on abstractions that hide those mechanics.
