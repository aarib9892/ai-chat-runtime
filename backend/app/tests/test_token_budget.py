def test_app_limit_wins_when_smaller():
    result = calculate_input_token_budget(
        model_context_window=128_000,
        max_output_tokens=2_000,
        app_max_input_tokens=8_000,
        safety_margin_tokens=500,
    )

    assert result == 8_000


def test_model_limit_wins_when_smaller():
    result = calculate_input_token_budget(
        model_context_window=10_000,
        max_output_tokens=2_000,
        app_max_input_tokens=9_000,
        safety_margin_tokens=500,
    )

    assert result == 7_500


def calculate_input_token_budget(
    *,
    model_context_window: int,
    max_output_tokens: int,
    app_max_input_tokens: int,
    safety_margin_tokens: int,
) -> int:
    hard_limit = model_context_window - max_output_tokens - safety_margin_tokens

    return min(
        app_max_input_tokens,
        hard_limit,
    )
