import os

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "YOUR_CURRENT_MODEL",
)

# Hard capability of the exact model you're using.
MODEL_CONTEXT_WINDOW = 128_000

# Maximum output WE want to allow for this app.
MAX_OUTPUT_TOKENS = 2_000

# Our own application-level input ceiling.
# This controls cost + latency even if the model
# supports a much larger context window.
APP_MAX_INPUT_TOKENS = 8_000

# Extra room for token-estimation differences,
# protocol overhead, etc.
SAFETY_MARGIN_TOKENS = 500
HARD_INPUT_LIMIT = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN_TOKENS

INPUT_TOKEN_BUDGET = min(
    APP_MAX_INPUT_TOKENS,
    HARD_INPUT_LIMIT,
)
TOKEN_ESTIMATION_BUFFER = 0.05
PLANNING_INPUT_BUDGET = int(INPUT_TOKEN_BUDGET * (1 - TOKEN_ESTIMATION_BUFFER))
# Keep summaries compact.
SUMMARY_MAX_OUTPUT_TOKENS = 800

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
