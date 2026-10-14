# openai_client.py

from openai import AsyncOpenAI

from app.config.settings import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)
