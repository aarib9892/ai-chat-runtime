# Agent evaluation

`backend/app/evals/agent_eval.py` evaluates the bounded multi-step agent loop with live Responses API calls. It checks the emitted event sequence, tool outcomes, terminal state, step count, incomplete reason, and selected properties of the final answer.

## Coverage

The seven scenarios cover:

1. A calculation followed by a text-length tool call.
2. A single successful calculation.
3. A direct answer with no tool call.
4. Recovery after a controlled divide-by-zero tool failure.
5. The maximum-agent-steps guard.
6. The maximum-total-tool-calls guard.
7. The repeated-tool-call guard path.

The final three scenarios pass lower per-run safety limits to `stream_agent`. Production callers continue to use the defaults: five agent steps, eight total tool calls, and two equivalent tool calls.

## Run

From `backend/`, run:

```bash
uv run python -m app.evals.agent_eval
```

The command returns a nonzero exit status when any scenario fails. It sends live requests to the configured OpenAI model and incurs provider usage, but it does not write to the application database. Keep it out of routine offline CI unless live-model evaluation is intentionally enabled.

For the runtime lifecycle and persistence model, see [the agent-loop guide](agent-loop.md).
