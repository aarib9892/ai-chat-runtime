import pytest

from app.runtime.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(
        limit=2,
        window_seconds=60,
    )

    assert await limiter.allow("client-a")
    assert await limiter.allow("client-a")


@pytest.mark.asyncio
async def test_rate_limiter_rejects_over_limit():
    limiter = RateLimiter(
        limit=2,
        window_seconds=60,
    )

    assert await limiter.allow("client-a")
    assert await limiter.allow("client-a")

    assert not await limiter.allow("client-a")


@pytest.mark.asyncio
async def test_rate_limits_are_per_client():
    limiter = RateLimiter(
        limit=1,
        window_seconds=60,
    )

    assert await limiter.allow("client-a")

    assert not await limiter.allow("client-a")

    assert await limiter.allow("client-b")
