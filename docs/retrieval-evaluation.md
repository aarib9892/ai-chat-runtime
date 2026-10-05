# Retrieval evaluation

`backend/app/evals/retrieval_eval.py` measures retrieval quality against the acid-rain fixture questions defined in the script. It reports Hit@1, Hit@3, and the rejection rate for unrelated questions.

Before running it, apply the migrations, create a document containing the fixture material, chunk it, and generate its embeddings. Then run the evaluator with that document’s UUID:

```bash
cd backend
uv run --with asyncpg --with openai \
  python -m app.evals.retrieval_eval --document-id <document-uuid>
```

The evaluator makes embedding API requests and queries the configured PostgreSQL database. It is intended for deliberate local evaluation rather than the normal test suite.
