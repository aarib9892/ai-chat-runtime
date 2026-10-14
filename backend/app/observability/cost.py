from app.config.settings import settings


def estimate_openai_cost_usd(
    input_tokens: int,
    output_tokens: int,
) -> float:

    input_cost = input_tokens / 1_000_000 * settings.openai_input_cost_per_1m_usd

    output_cost = output_tokens / 1_000_000 * settings.openai_output_cost_per_1m_usd

    return input_cost + output_cost
