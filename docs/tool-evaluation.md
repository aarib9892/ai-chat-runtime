# Tool evaluation

`backend/app/evals/tool_eval.py` measures whether the configured model selects the expected tool, produces the expected arguments, and produces the expected result through the real tool runtime.

## Coverage

The suite contains ten live model requests:

- Four arithmetic-routing cases: addition, subtraction, multiplication, and division.
- Two text-length cases, including punctuation and spaces.
- One divide-by-zero case that must route to the calculator and report a controlled execution error.
- Three prompts that should be answered without a tool.

Addition and multiplication arguments may arrive in either operand order because those operations are commutative. Other argument checks require the expected order.

## Run it

From `backend/`, run:

```bash
uv run python -m app.evals.tool_eval
```

The command requires `OPENAI_API_KEY` and a configured `OPENAI_MODEL`. It sends live OpenAI requests, so it incurs provider usage and may vary with model behavior. It does not write to the application database.

The process exits with status `0` only when every case passes, making it suitable for an explicit CI step once the expected pass-rate policy is defined.
