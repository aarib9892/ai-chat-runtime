# Runtime reliability and observability

The conversation endpoint has process-local safeguards for overload, structured errors for clients, and persisted usage data for completed agent responses.

## Request and provider errors

Every HTTP response receives an `X-Request-ID` header. If the caller supplies a valid ASCII identifier (letters, digits, `.`, `_`, or `-`, up to 128 characters), the service preserves it; otherwise it creates one. The header is exposed to allowed CORS origins. Validation and application errors use this envelope:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please try again shortly.",
    "retryable": true,
    "request_id": "..."
  }
}
```

Provider rate limits, timeouts, connection failures, and other provider status failures are mapped to retryable application errors. Errors produced after a stream begins use the existing NDJSON `error` event with `code`, `message`, and `retryable`; use the response's `X-Request-ID` header to correlate it with logs.

## Overload controls

- `ASK_RATE_LIMIT` limits `/ask` requests per client IP in each `ASK_RATE_WINDOW_SECONDS` window. Defaults: 20 requests per 60 seconds.
- `MAX_CONCURRENT_AGENT_RUNS` limits active agent runs in this process. Default: 10.
- `AGENT_QUEUE_TIMEOUT_SECONDS` bounds how long a request waits for a slot. Default: 5 seconds.
- Migration `008_agent_runtime_observability.sql` enforces one streaming assistant response per conversation. A second request receives `CONVERSATION_BUSY` (409).

The limiter and semaphore are in-process controls. Deployments with multiple backend instances need a shared, edge, or database-backed limiter/concurrency mechanism for global enforcement.

## Usage data

For each completed agent run, the runtime aggregates the Responses API `usage` values from every agent step. Migration 008 adds per-step duration and token columns to `message_agent_steps` and creates `message_usage` for total tokens, model-call count, duration, configured model, and estimated cost.

Cost estimation uses these environment variables, expressed in USD per one million tokens:

- `OPENAI_INPUT_COST_PER_1M_USD`
- `OPENAI_OUTPUT_COST_PER_1M_USD`

Both default to `0`, so estimates remain zero until the deployment sets model-specific prices. This is an operational estimate, not an invoice.

## Deploy

Apply migrations through `008_agent_runtime_observability.sql` in order while the application is not processing requests. Before applying migration 008 to an existing database, ensure no conversation has more than one assistant message with status `streaming`, because the migration adds a partial unique index for that invariant.

See [the agent-loop guide](agent-loop.md) for the multi-step execution model.
