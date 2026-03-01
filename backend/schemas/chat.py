"""Pydantic schemas for chat-related requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BookRecommendation(BaseModel):
    book_id: str
    title: str
    author: str
    explanation: str
    cover_url: Optional[str] = None
    avg_rating: Optional[float] = None


class ChatMessageRequest(BaseModel):
    student_id: str
    session_id: Optional[str] = None  # None = create new session
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    message: str
    session_id: str
    recommendations: Optional[List[BookRecommendation]] = None
    guardrail_triggered: bool = False


class ChatMessageDetail(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None


class ChatSessionCreate(BaseModel):
    student_id: str


class ChatSessionResponse(BaseModel):
    id: int
    student_id: str
    thread_id: str
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    messages: List[ChatMessageDetail] = []

    model_config = {"from_attributes": True}
