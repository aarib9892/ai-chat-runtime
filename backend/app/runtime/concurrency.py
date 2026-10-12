import asyncio

from app.config.settings import (
    MAX_CONCURRENT_AGENT_RUNS,
)

agent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENT_RUNS)
