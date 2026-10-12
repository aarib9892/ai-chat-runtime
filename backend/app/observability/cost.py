from app.config.settings import (
    OPENAI_INPUT_COST_PER_1M_USD,
    OPENAI_OUTPUT_COST_PER_1M_USD,
)


def estimate_openai_cost_usd(
    input_tokens: int,
    output_tokens: int,
) -> float:

    input_cost = input_tokens / 1_000_000 * OPENAI_INPUT_COST_PER_1M_USD

    output_cost = output_tokens / 1_000_000 * OPENAI_OUTPUT_COST_PER_1M_USD

    return input_cost + output_cost
