from app.config.settings import settings
from app.config.model_capabilities import (
    get_model_context_window,
)

MODEL_CONTEXT_WINDOW = get_model_context_window(settings.openai_model)

HARD_INPUT_LIMIT = (
    MODEL_CONTEXT_WINDOW - settings.max_output_tokens - settings.safety_margin_tokens
)

INPUT_TOKEN_BUDGET = min(
    settings.app_max_input_tokens,
    HARD_INPUT_LIMIT,
)

PLANNING_INPUT_BUDGET = int(INPUT_TOKEN_BUDGET * (1 - settings.token_estimation_buffer))
