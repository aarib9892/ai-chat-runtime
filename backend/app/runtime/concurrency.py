import asyncio

from app.config.settings import settings

agent_semaphore = asyncio.Semaphore(settings.max_concurrent_agent_runs)
