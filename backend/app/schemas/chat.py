from pydantic import BaseModel
from typing import Literal


class ChatMessage(BaseModel):
    content: str
    role: Literal["user", "assistant"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
