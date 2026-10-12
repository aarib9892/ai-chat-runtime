from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_INPUT_COST_PER_1M_USD = float(
    os.getenv(
        "OPENAI_INPUT_COST_PER_1M_USD",
        "0",
    )
)

OPENAI_OUTPUT_COST_PER_1M_USD = float(
    os.getenv(
        "OPENAI_OUTPUT_COST_PER_1M_USD",
        "0",
    )
)

MAX_CONCURRENT_AGENT_RUNS = int(
    os.getenv(
        "MAX_CONCURRENT_AGENT_RUNS",
        "10",
    )
)
AGENT_QUEUE_TIMEOUT_SECONDS = float(
    os.getenv(
        "AGENT_QUEUE_TIMEOUT_SECONDS",
        "5",
    )
)
ASK_RATE_LIMIT = int(
    os.getenv(
        "ASK_RATE_LIMIT",
        "20",
    )
)

ASK_RATE_WINDOW_SECONDS = float(
    os.getenv(
        "ASK_RATE_WINDOW_SECONDS",
        "60",
    )
)
