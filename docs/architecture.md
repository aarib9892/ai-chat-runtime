# AI Chat Runtime — Architecture

This document describes the internal architecture of `ai-chat-runtime`, with emphasis on request flow, streaming, persistence, context management, RAG, tool execution, the agent loop, safeguards, observability, and transaction boundaries.

The goal is to make the runtime behavior explicit and inspectable rather than hiding it behind a large orchestration framework.

---

## 1. System Overview

At a high level, the application is split into four major runtime areas:

```text
Browser / React UI
        ↓
Nginx reverse proxy
        ↓
FastAPI application
        ↓
PostgreSQL + pgvector
```

The FastAPI backend contains the AI runtime:

```text
HTTP/API layer
    ↓
application services
    ↓
context / retrieval / agent runtime
    ↓
repositories
    ↓
PostgreSQL + pgvector
```

External model calls are made through the OpenAI Responses API.

---

## 2. High-Level Deployment Architecture

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

The frontend only talks to Nginx.

Nginx serves the built React application and proxies `/api/*` requests to FastAPI.

PostgreSQL is not exposed publicly by default.

---

## 3. Backend Layering

The backend is intentionally split into distinct responsibilities.

```text
API layer
    ↓
application/service layer
    ↓
runtime logic
    ↓
repository layer
    ↓
database
```

Typical responsibilities:

### API layer

Handles:

- HTTP request parsing
- validation
- routing
- response construction
- streaming responses

### Services

Handles application workflows such as:

- conversation ask flow
- context planning
- retrieval integration
- streaming orchestration
- telemetry persistence

### Runtime

Handles behavior such as:

- agent execution loop
- rate limiting
- concurrency controls
- token budgeting
- tool execution

### Repositories

Handles database persistence for:

- conversations
- messages
- summaries
- sources
- tool calls
- agent steps
- usage telemetry

This separation keeps transport, persistence, and AI orchestration independent.

---

## 4. `/ask` Request Lifecycle

The central request path is:

```text
POST /api/conversations/{conversation_id}/ask
```

A typical request follows this flow:

```text
HTTP request
    ↓
rate limiting
    ↓
conversation lookup
    ↓
global agent slot acquisition
    ↓
short DB transaction
    │
    ├── insert user message
    └── insert assistant placeholder
    ↓
optional summary planning
    ↓
context construction
    ↓
optional RAG retrieval
    ↓
stream_agent()
    ↓
model/tool loop
    ↓
NDJSON events
    ↓
React UI
    ↓
assistant persistence
    ↓
usage telemetry
    ↓
release concurrency slot
```

The request intentionally avoids holding a database transaction open while waiting for the model.

---

## 5. Rate Limiting

The `/ask` endpoint applies rate limiting before expensive work begins.

The current limiter is:

- in-memory
- keyed by client identity
- protected by an async lock
- fixed-window based

Conceptually:

```text
client request
    ↓
rate limiter
    ├── allowed → continue
    └── rejected → RATE_LIMITED
```

The current implementation is process-local.

For horizontally scaled production deployment, the limiter would need a shared store such as Redis.

---

## 6. Conversation Concurrency Protection

The application prevents multiple simultaneous assistant streams for the same conversation.

This is enforced at the database level using a partial unique index on streaming assistant messages.

Conceptually:

```text
conversation
    ↓
existing streaming assistant?
    ├── yes → CONVERSATION_BUSY
    └── no  → continue
```

This protects conversation consistency even if application-level checks race.

---

## 7. Global Agent Concurrency

A semaphore limits the number of active agent runs:

```text
MAX_CONCURRENT_AGENT_RUNS
```

Requests wait up to:

```text
AGENT_QUEUE_TIMEOUT_SECONDS
```

If no slot becomes available, the request fails with:

```text
SERVER_BUSY
```

The endpoint owns the semaphore slot until ownership is transferred to the streaming generator.

The streaming generator releases the slot in `finally`, which protects against leaks on:

- normal completion
- cancellation
- provider errors
- unexpected exceptions

---

## 8. Persistence Model

The runtime persists multiple categories of state.

### Conversations

Represents the top-level conversation identity.

Typical fields:

```text
id
title
created_at
updated_at
```

### Messages

Represents user and assistant messages.

Assistant messages have lifecycle states:

```text
streaming
completed
stopped
error
incomplete
```

Only completed assistant messages are included in future model context.

### Conversation summaries

Stores rolling summaries for long conversations.

Important fields include:

```text
conversation_id
summary
through_message_id
token_count
updated_at
```

The `through_message_id` boundary prevents accidentally summarizing the same messages twice.

### Message sources

Stores RAG source attribution separately from normal conversation messages.

### Agent steps

One row represents one model response/decision in the agent loop.

Typical fields:

```text
message_id
step_number
provider_response_id
status
outcome
duration_ms
input_tokens
output_tokens
total_tokens
```

### Tool calls

Tool calls are persisted separately from agent steps.

Typical fields:

```text
message_id
step_number
call_id
tool_name
arguments
result
status
error
```

### Message usage

Stores aggregate model telemetry for the assistant turn.

Typical fields:

```text
message_id
model
model_calls
input_tokens
output_tokens
total_tokens
duration_ms
estimated_cost_usd
```

---

## 9. Message Lifecycle

An assistant response moves through explicit states.

```text
streaming
   │
   ├── completed
   ├── stopped
   ├── incomplete
   └── error
```

These states mean different things.

### completed

The assistant finished normally.

### stopped

Generation was cancelled by the user.

### incomplete

The runtime intentionally stopped the agent because of a safeguard.

Examples:

```text
max_agent_steps
max_tool_calls
repeated_tool_call
```

### error

A runtime, infrastructure, provider, or internal failure occurred.

This distinction is important because an `incomplete` response is not the same as a system failure.

---

## 10. Streaming Architecture

The application uses structured NDJSON rather than streaming raw text.

The path is:

```text
OpenAI stream event
        ↓
agent domain event
        ↓
FastAPI async generator
        ↓
NDJSON line
        ↓
Nginx
        ↓
browser ReadableStream
        ↓
React reducer/state
```

Example stream events:

```json
{"type":"message_ids","user_message_id":"...","assistant_message_id":"..."}
{"type":"agent_step_started","step":1}
{"type":"response_id","response_id":"..."}
{"type":"tool_call","step":1,"name":"calculate"}
{"type":"tool_result","step":1,"name":"calculate"}
{"type":"delta","delta":"The result is "}
{"type":"delta","delta":"42"}
{"type":"done"}
```

Other events include:

```text
sources
agent_step_completed
tool_error
incomplete
error
```

The frontend can therefore distinguish runtime events from model text.

---

## 11. Why NDJSON

NDJSON gives the stream a structured protocol.

Without structured events, the frontend would only know:

```text
"some text arrived"
```

With NDJSON, it can distinguish:

```text
assistant text
tool activity
agent step progress
retrieval sources
completion
controlled termination
runtime failure
```

This enables a richer UI and cleaner state management.

---

## 12. Cancellation

The frontend uses `AbortController`.

Conceptually:

```text
user clicks Stop
    ↓
AbortController.abort()
    ↓
HTTP stream cancelled
    ↓
backend cancellation propagates
    ↓
assistant persisted as stopped
    ↓
resources released
```

Cancellation is not treated as an internal error.

---

## 13. Context Management

The application does not send unlimited conversation history to the model.

It calculates a token budget.

```text
MODEL_CONTEXT_WINDOW
        ↓
- MAX_OUTPUT_TOKENS
        ↓
- SAFETY_MARGIN_TOKENS
        ↓
HARD_INPUT_LIMIT
        ↓
min(APP_MAX_INPUT_TOKENS, HARD_INPUT_LIMIT)
        ↓
INPUT_TOKEN_BUDGET
        ↓
apply token estimation buffer
        ↓
PLANNING_INPUT_BUDGET
```

Recent messages are selected within this budget.

The current user prompt is always treated as mandatory.

---

## 14. Rolling Conversation Summaries

Long-running conversations use a rolling summary.

Conceptually:

```text
older completed messages
        ↓
summary threshold reached
        ↓
summary model call
        ↓
conversation_summaries
        ↓
future context =
summary + recent raw messages
```

The system keeps recent messages verbatim while compressing older history.

This controls:

- token usage
- latency
- context-window pressure
- provider cost

Summary failure is treated as non-fatal so the core chat path can continue.

---

## 15. RAG Architecture

The retrieval pipeline is implemented directly.

```text
document
    ↓
token chunking
    ↓
embedding generation
    ↓
document_chunks
    ↓
pgvector
    ↓
cosine similarity search
    ↓
threshold
    ↓
retrieved context
```

The system currently uses:

```text
text-embedding-3-small
1536 dimensions
```

The embedding configuration is centralized in runtime settings.

---

## 16. Document Chunking

Documents are split using token-aware chunking.

Typical configuration:

```text
chunk size: 400 tokens
overlap:    80 tokens
```

Overlap helps preserve context across chunk boundaries.

The chunker guards against invalid overlap or loops that would otherwise fail to advance.

---

## 17. Vector Search

Retrieval uses pgvector cosine distance.

Conceptually:

```sql
1 - (embedding <=> query_embedding)
```

produces similarity.

The search is:

- document-scoped
- embedding-model aware
- ordered by nearest distance
- limited to top-K
- filtered by similarity threshold

This allows irrelevant queries to return no context.

---

## 18. RAG Context vs Conversation Memory

Retrieved knowledge is not stored as normal conversation messages.

Instead:

```text
conversation history
        +
rolling summary
        +
transient retrieved evidence
        ↓
model input
```

This prevents retrieved source text from becoming accidental long-term conversational memory.

Source attribution is persisted separately.

---

## 19. Tool Architecture

Tools are registered explicitly.

Conceptually:

```python
ToolSpec(
    handler=...,
    args_model=...,
)
```

Each tool has:

- a schema exposed to the model
- a Pydantic validation model
- a deterministic handler
- structured execution output

Example tools:

```text
calculate
get_text_length
```

---

## 20. Tool Execution Flow

```text
model requests tool
        ↓
lookup tool registry
        ↓
parse arguments
        ↓
Pydantic validation
        ↓
execute handler
        ↓
ToolExecutionResult
        ↓
JSON string
        ↓
function_call_output
        ↓
next model step
```

Tool output sent back to the model must be a JSON string.

Example:

```json
{ "result": 76728 }
```

or:

```json
{ "error": "Cannot divide by zero." }
```

---

## 21. Tool Failures Are Observations

Tool failures are not automatically agent failures.

Example:

```text
model
  ↓
calculate(10 / 0)
  ↓
tool error
  ↓
error observation returned to model
  ↓
model explains the problem
  ↓
agent completes normally
```

This lets the model recover when the failure is understandable and non-fatal.

---

## 22. Agent Runtime

The agent runtime is an explicit loop.

```text
while not finished:
    call model

    if final answer:
        complete

    if tool call:
        execute tool
        append observation
        continue
```

One agent step represents one model response/decision.

A tool call is an action requested during that step.

These are separate concepts in both runtime events and persistence.

---

## 23. Streaming Agent Events

The agent runtime emits typed domain events such as:

```text
AgentStepStarted
AgentResponseCreated
AgentTextDelta
AgentToolCall
AgentToolResult
AgentToolError
AgentStepCompleted
AgentCompleted
AgentIncomplete
```

The service layer translates these into NDJSON events and persistence operations.

This keeps the core agent runtime independent from:

- FastAPI
- PostgreSQL
- frontend protocol details

---

## 24. Agent Safeguards

The runtime enforces:

```text
MAX_AGENT_STEPS
MAX_AGENT_TOOL_CALLS
MAX_IDENTICAL_TOOL_CALLS
```

Safeguards are checked before tool execution.

This prevents:

- runaway loops
- repeated identical tool calls
- excessive tool usage
- uncontrolled model/tool recursion

When a safeguard is triggered, the agent emits `AgentIncomplete`.

---

## 25. Repeated Tool Call Protection

Tool signatures are normalized deterministically using:

```text
tool name
+
sorted JSON arguments
```

This lets the runtime detect repeated identical calls.

Example:

```text
calculate({"a":10,"b":20,"operation":"multiply"})
```

If the same signature exceeds the configured limit, the runtime stops with:

```text
repeated_tool_call
```

---

## 26. Error Taxonomy

Application errors use explicit codes.

Examples:

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

This gives the frontend stable error semantics.

---

## 27. Pre-Stream vs Mid-Stream Errors

Before response headers are committed, errors can use normal HTTP status codes.

Example:

```text
404 CONVERSATION_NOT_FOUND
429 RATE_LIMITED
503 SERVER_BUSY
```

After streaming begins, HTTP status is already committed.

Mid-stream failures therefore use NDJSON:

```json
{
  "type": "error",
  "code": "PROVIDER_TIMEOUT",
  "message": "The model provider timed out.",
  "retryable": true
}
```

---

## 28. Provider Error Mapping

OpenAI SDK errors are mapped into application errors.

Examples:

```text
RateLimitError
    → PROVIDER_RATE_LIMITED

APITimeoutError
    → PROVIDER_TIMEOUT

APIConnectionError
    → PROVIDER_UNAVAILABLE

APIStatusError
    → PROVIDER_ERROR
```

Only explicit provider SDK errors are mapped this way.

Unexpected application bugs remain internal errors.

---

## 29. Request Tracing

Every request receives a request ID.

The middleware:

- accepts an incoming request ID if present
- otherwise generates one
- stores it in a ContextVar
- returns it in the response header
- makes it available to structured logs

Example response header:

```text
x-request-id: 7b533cbc-...
```

This makes a single request traceable across the backend.

---

## 30. Structured Logging

Logs are JSON structured records.

Typical fields include:

```text
timestamp
level
logger
message
request_id
conversation_id
assistant_message_id
step
outcome
duration_ms
input_tokens
output_tokens
total_tokens
status
```

The application avoids logging sensitive contents such as:

```text
API keys
authorization headers
cookies
full prompts
retrieved chunk text
full model output
arbitrary tool arguments
```

---

## 31. Usage and Latency Telemetry

Each model step records:

```text
duration_ms
input_tokens
output_tokens
total_tokens
```

The final assistant message stores aggregate values:

```text
model
model_calls
input_tokens
output_tokens
total_tokens
duration_ms
estimated_cost_usd
```

`model_calls` currently corresponds to the number of agent steps because each step represents one model response.

---

## 32. Cost Estimation

Provider cost is configuration-driven.

The runtime reads:

```text
OPENAI_INPUT_COST_PER_1M_USD
OPENAI_OUTPUT_COST_PER_1M_USD
```

instead of hard-coding provider prices into business logic.

This allows pricing configuration to change independently from code.

---

## 33. Telemetry Failure Policy

Telemetry is not allowed to invalidate an otherwise successful assistant response.

Conceptually:

```text
assistant persistence fails
    → critical failure

usage telemetry persistence fails
    → log failure
    → assistant response remains successful
```

Observability should observe the application, not become a single point of failure.

---

## 34. Database Transaction Boundaries

Long-running model generation is kept outside database transactions.

The runtime uses short transactions for operations such as:

```text
create user message
create assistant placeholder
persist assistant completion
persist tool state
persist agent step state
```

This avoids holding:

- locks
- connections
- transactions

while waiting for external model calls.

---

## 35. Production Configuration

Configuration is centralized through `pydantic-settings`.

Examples include:

```text
DATABASE_URL
OPENAI_API_KEY
OPENAI_MODEL

MAX_OUTPUT_TOKENS
APP_MAX_INPUT_TOKENS
SAFETY_MARGIN_TOKENS

MAX_AGENT_STEPS
MAX_AGENT_TOOL_CALLS
MAX_IDENTICAL_TOOL_CALLS

MAX_CONCURRENT_AGENT_RUNS
AGENT_QUEUE_TIMEOUT_SECONDS

ASK_RATE_LIMIT
ASK_RATE_WINDOW_SECONDS

EMBEDDING_MODEL
EMBEDDING_DIMENSIONS

CORS_ORIGINS
LOG_LEVEL
ENVIRONMENT
```

Invalid required configuration fails at startup.

---

## 36. Model Capabilities vs Runtime Policy

Hard model facts are kept separate from application policy.

Example:

```text
model context window
```

is a model capability.

Values such as:

```text
APP_MAX_INPUT_TOKENS
MAX_OUTPUT_TOKENS
SAFETY_MARGIN_TOKENS
```

are application policy.

This avoids silently combining configuration for one model with capabilities from another.

---

## 37. Docker Architecture

The application runs as multiple containers:

```text
db
    PostgreSQL + pgvector

migrate
    one-shot migration runner

backend
    FastAPI + AI runtime

frontend
    React production build + Nginx
```

Startup ordering is:

```text
db healthy
    ↓
migrate succeeds
    ↓
backend starts
    ↓
frontend serves UI
```

---

## 38. Database Migration Strategy

SQL migrations are stored under:

```text
backend/migrations/
```

The migration runner keeps a:

```text
schema_migrations
```

table.

Each migration filename is recorded after successful execution.

This allows a completely fresh PostgreSQL database to be bootstrapped without manual SQL execution.

---

## 39. Nginx Streaming Configuration

Nginx proxies `/api/*` to FastAPI.

Buffering is disabled for the streaming path.

Conceptually:

```nginx
proxy_buffering off;
proxy_cache off;
```

Without this, Nginx could buffer NDJSON chunks and make streaming appear as one large response.

---

## 40. Health Endpoints

The backend exposes:

```text
/health/live
/health/ready
```

`/health/live` verifies that the process is alive.

`/health/ready` verifies that the application can communicate with PostgreSQL.

Nginx exposes:

```text
/health/backend
```

which proxies to backend readiness.

---

## 41. Evaluation Architecture

The project separates deterministic and probabilistic testing.

### Deterministic tests

`pytest` covers:

```text
configuration validation
rate limiting
token budgeting
tool serialization
provider error mapping
```

### RAG eval

Checks:

```text
Hit@1
Hit@3
negative-query rejection
```

### Agent eval

Checks:

```text
tool sequence
tool success/failure
step count
terminal state
safeguard termination
final answer
```

### API smoke test

Checks the real HTTP path:

```text
Nginx
  ↓
FastAPI
  ↓
streaming
  ↓
OpenAI
  ↓
PostgreSQL
  ↓
conversation reload
```

---

## 42. Current Quality Gate

The project quality gate covers:

```text
18 deterministic regression tests
12 RAG evaluation cases
7 agent evaluation cases
1 end-to-end API smoke flow
```

A successful run ends with:

```text
Tests: PASS
RAG:   PASS
Agent: PASS
API:   PASS

QUALITY GATE: PASS
```

---

## 43. Current Limitations

The runtime intentionally keeps some areas simple:

- rate limiting is process-local
- tools execute sequentially
- `parallel_tool_calls` is disabled
- authentication is not implemented
- RAG evals rely on a known embedded fixture
- horizontal scaling requires shared rate-limit state
- production proxy trust must be configured carefully
- tool examples are intentionally deterministic and small

These are explicit boundaries rather than hidden assumptions.

---

## 44. Architectural Principles

The project follows a few core principles:

### Keep runtime mechanics visible

Avoid hiding context planning, retrieval, and agent loops behind large abstractions.

### Separate deterministic logic from model behavior

Use unit tests for deterministic logic and evals for probabilistic AI behavior.

### Keep database transactions short

Do not wrap external model calls in long transactions.

### Persist execution state explicitly

Messages, agent steps, tools, sources, and usage each have distinct persistence models.

### Treat tool failures as data

A failed tool call can be an observation the model reasons about.

### Distinguish incomplete from error

A safeguard-triggered stop is expected runtime behavior, not a crash.

### Observability must not become a critical dependency

Telemetry failures should not invalidate a successfully completed assistant response.
