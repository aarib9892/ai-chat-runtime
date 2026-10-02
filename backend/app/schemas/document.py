from pydantic import BaseModel


class DocumentCreate(BaseModel):
    filename: str
    content: str
    mime_type: str | None = "text/plain"
