import asyncio
import time
from dataclasses import dataclass

from app.config.settings import settings


@dataclass
class RateBucket:
    window_started_at: float
    count: int


class RateLimiter:

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
    ):
        self.limit = limit
        self.window_seconds = window_seconds

        self._buckets: dict[
            str,
            RateBucket,
        ] = {}

        self._lock = asyncio.Lock()

    async def allow(
        self,
        key: str,
    ) -> bool:

        now = time.monotonic()

        async with self._lock:
            bucket = self._buckets.get(key)

            if bucket is None or now - bucket.window_started_at >= self.window_seconds:
                self._buckets[key] = RateBucket(
                    window_started_at=now,
                    count=1,
                )

                return True

            if bucket.count >= self.limit:
                return False

            bucket.count += 1

            return True


ask_rate_limiter = RateLimiter(
    limit=settings.ask_rate_limit,
    window_seconds=settings.ask_rate_window_seconds,
)
