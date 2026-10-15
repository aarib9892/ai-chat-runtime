import httpx

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from app.errors import ErrorCode
from app.services.provider_errors import (
    map_openai_error,
)


def make_request() -> httpx.Request:
    return httpx.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )


def test_provider_timeout_mapping():
    exc = APITimeoutError(
        request=make_request(),
    )

    mapped = map_openai_error(exc)

    assert mapped.code == ErrorCode.PROVIDER_TIMEOUT
    assert mapped.retryable is True


def test_provider_connection_error_mapping():
    exc = APIConnectionError(
        request=make_request(),
    )

    mapped = map_openai_error(exc)

    assert mapped.code == ErrorCode.PROVIDER_UNAVAILABLE

    assert mapped.retryable is True


def test_provider_rate_limit_mapping():
    request = make_request()

    response = httpx.Response(
        status_code=429,
        request=request,
    )

    exc = RateLimitError(
        "rate limited",
        response=response,
        body=None,
    )

    mapped = map_openai_error(exc)

    assert mapped.code == ErrorCode.PROVIDER_RATE_LIMITED

    assert mapped.retryable is True


def test_provider_status_error_mapping():
    request = make_request()

    response = httpx.Response(
        status_code=500,
        request=request,
    )

    exc = APIStatusError(
        "provider failed",
        response=response,
        body=None,
    )

    mapped = map_openai_error(exc)

    assert mapped.code == ErrorCode.PROVIDER_ERROR
