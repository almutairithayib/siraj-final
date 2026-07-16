import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class ChatSessionCreate(BaseModel):
    title: str | None = None

class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageCreate(BaseModel):
    content: str

class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str  # user, assistant, tool
    content: str | None = None
    tool_metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True
