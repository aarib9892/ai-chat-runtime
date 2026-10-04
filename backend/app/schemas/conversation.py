from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str | None = None


class MessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    message: str
    document_id: UUID | None = None
