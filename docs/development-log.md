# Development log

Use this file as an append-only record of meaningful implementation work. Add a dated entry for each completed slice, noting the user-visible result, important implementation details, and validation performed.

## 2026-09-30 — Token-aware persisted streaming

### Completed

- Made creation of a user message, its streaming assistant placeholder, an automatic conversation title, and the activity timestamp a single database transaction.
- Added optional database connections to message and conversation repository writes so transactional callers use the same connection; existing non-transactional callers continue to use the pool.
- Sent a `message_ids` NDJSON event before stream deltas and updated the React reducer to replace optimistic message IDs with their persisted IDs.
- Replaced the fixed message-count context window with token-aware history selection. The current user message is always retained, and completed history is added newest-first within the planning budget.
- Added configurable model and token-limit settings, `tiktoken` token counting, OpenAI output-token limits, and estimated-versus-actual token-usage logging.
- Moved the backend uv project files from `backend/app/` to `backend/` and updated the root setup guide accordingly.

### Validation

- `python -m compileall -q backend/app` completed successfully using the backend virtual environment.
- The backend virtual environment can import `asyncpg`, `openai`, `dotenv`, and `tiktoken`.
- ESLint and a targeted TypeScript type check passed for the changed chat hook, reducer, and stream-event types.
- Full frontend lint and build are currently blocked by pre-existing JSX syntax in `frontend/react-frontend/src/AppChaining.ts`, which is outside this change set.

### Follow-up

- Add focused backend tests for transaction rollback and token-budget boundary cases.
- Repair or rename `AppChaining.ts` to unblock the full frontend lint/build check.
