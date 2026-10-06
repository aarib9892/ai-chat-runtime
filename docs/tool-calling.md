# Tool calling

The chat runtime can ask the model to call a small, server-owned set of tools while it is producing a response. Tool invocations are recorded against the assistant message so they remain visible after a conversation is reopened.

## Available tools

- `calculate`: add, subtract, multiply, or divide two numbers.
- `get_text_length`: count the characters in a supplied string.

The tool registry is allow-listed in `backend/app/tools/registry.py`. Adding a tool requires a strict OpenAI function definition in `definitions.py`, an implementation, and an explicit registry entry; model-provided function names are never imported or executed dynamically.

## Request flow

1. The model emits one function call. Parallel calls are disabled.
2. The backend saves the call with a `running` status and streams a `tool_call` NDJSON event.
3. The registered handler runs with the model's JSON arguments.
4. The backend saves either a `completed` result or an `error`, streams a `tool_result` event, and gives the serialized outcome to the model for its final response.
5. The restored-conversation API returns each assistant message's tool calls along with sources, and the React client renders their arguments, outcome, and status.

Tool execution errors are passed back to the model as an error object, allowing it to give the user a useful response instead of leaving a persisted tool call in `running` state.

## Database migration

Apply `backend/migrations/006_message_tool_calls.sql` after migrations 001–005. It creates `message_tool_calls`, including arguments, result, status, error details, timestamps, and a uniqueness constraint on the message/call pair.

## Manual evaluation

From `backend/`, run:

```bash
uv run python -m app.evals.tool_call_test
```

This sends three live OpenAI requests and exercises arithmetic and text-length calls. It requires `OPENAI_API_KEY` and a configured `OPENAI_MODEL`; it does not write to the application database.

## Current scope

Each model turn supports one sequential tool call. Multi-tool planning and parallel calls can be added later if a product workflow needs them.
