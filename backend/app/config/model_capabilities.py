MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-6-astra": 1_050_000,
    "gpt-6.1-sol": 1_050_000,
    "gpt-6-luna": 1_050_000,
}


def get_model_context_window(
    model: str,
) -> int:
    try:
        return MODEL_CONTEXT_WINDOWS[model]
    except KeyError:
        raise ValueError(f"Unknown context window for model: {model}")
