# Agent tool loop

The chat runtime can now complete a bounded sequence of tool-assisted Responses API turns. This supports tasks that require the output of one tool before selecting the next tool, while keeping execution observable and recoverable.

## Execution model

1. The runtime starts an agent step and streams the model response.
2. If the model requests a tool, the call is persisted with its step number, executed through the validated tool registry, and streamed to the client.
3. The serialized function output is sent to the next Responses API turn using the previous response ID.
4. The loop repeats until the model returns a final message or a safety bound is reached.

Parallel tool calls remain disabled. The runtime allows up to five model steps, eight total tool calls, and two identical calls with the same canonical arguments. Reaching a bound produces an incomplete response instead of continuing indefinitely.

`stream_agent` also accepts per-run versions of those three limits. They are intended for controlled evaluation and testing; normal application calls use the production defaults above. See [the agent evaluation guide](agent-evaluation.md) for the live scenarios that exercise each guard.

## Persistence and restoration

Migration `007_message_agent_steps.sql` adds a nullable `step_number` to existing `message_tool_calls` rows and creates `message_agent_steps`. Existing calls remain valid with no step number. New calls and agent responses record their step, provider response ID, status, outcome, start time, and completion time.

The restored conversation API includes `agent_steps` and per-tool `step` values. The client maps those snake-case API values into its conversation model, so the history is available after reload even when the live stream has ended.

## Manual live check

From `backend/`, run:

```bash
uv run python -m app.evals.agent_loop_test
```

The check asks the model to multiply `834 × 92` and then count the characters in the unformatted result. It makes live OpenAI requests and incurs provider usage, but does not write to the application database.

For a broader set of multi-step, no-tool, failure-recovery, and limit-guard checks, run:

```bash
uv run python -m app.evals.agent_eval
```
