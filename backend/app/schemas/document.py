from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    filename: str
    content: str
    mime_type: str | None = "text/plain"


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
