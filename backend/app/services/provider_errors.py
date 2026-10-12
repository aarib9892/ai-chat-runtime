import openai

from app.errors import (
    AppError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def map_openai_error(
    exc: Exception,
) -> AppError:

    if isinstance(
        exc,
        openai.RateLimitError,
    ):
        return ProviderRateLimitError()

    if isinstance(
        exc,
        openai.APITimeoutError,
    ):
        return ProviderTimeoutError()

    if isinstance(
        exc,
        openai.APIConnectionError,
    ):
        return ProviderUnavailableError()

    if isinstance(
        exc,
        openai.APIStatusError,
    ):
        return ProviderError()

    return ProviderError()
