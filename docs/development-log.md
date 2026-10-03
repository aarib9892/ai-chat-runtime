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

## 2026-10-01 — Rolling conversation summaries and incomplete responses

### Completed

- Added a `conversation_summaries` store that records a compact summary, its message boundary, token count, and update time for each conversation.
- Added a rolling-summary planner: after unsummarized completed history reaches the token trigger, it retains recent raw messages and replaces older turns with a concise OpenAI-generated summary.
- Included the persisted summary in context construction while ensuring that contexts without a summary do not contain an empty placeholder.
- Added the `incomplete` message state through the database migration, streaming service, stream-event types, reducer, and message UI. Responses ending because of an output limit now display a clear explanation.
- Updated the composer’s stop handler to use its local click event and removed development-only console logging.

### Validation

- Backend compilation and uv lock validation passed.
- Direct context-construction checks passed with and without a summary; summary-planning checks passed below and above the trigger threshold.
- ESLint and a targeted TypeScript type check passed for the changed chat components, stream hook, reducer, and types.

### Follow-up

- Run migration tests against an existing database as well as a clean database before deploying.

## 2026-10-02 — Document ingestion foundation

### Completed

- Added `documents` storage with filename, content, MIME type, and creation time.
- Added `document_chunks` storage, ordered per document and indexed for future chunking and retrieval workflows.
- Added `POST /api/documents`, which validates document input and persists it through the document repository.
- Registered the document router with the FastAPI application.
- Updated setup instructions to apply every migration for new databases and documented the new API route.

### Validation

- Backend compilation, route-registration, document-schema, repository, and uv lock checks passed without needing a live database.

### Follow-up

- Add document retrieval, chunking, token counting, and search before using uploaded documents as model context.

## 2026-10-03 — Document chunking and semantic search

### Completed

- Added token-based document chunking with configurable chunk size and overlap.
- Added OpenAI embedding generation using `text-embedding-3-small`, with dimension validation before persistence.
- Added pgvector registration for database connections, vector columns, a cosine-similarity index, and repository operations for embedding updates and nearest-neighbor search.
- Added chunk, embedding, and search API endpoints; search requests now require a non-empty query and a bounded result limit.
- Removed development-only output from token and document-processing paths, and updated the API documentation.

### Validation

- Backend compilation, chunking edge cases, API route registration, repository query construction, embedding-shape validation, and uv lock validation passed without requiring a live database or OpenAI request.

### Follow-up

- Add authenticated document ownership and batch large embedding requests before exposing ingestion to untrusted clients.
