"""Pydantic schemas for admin/librarian endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenUsageResponse(BaseModel):
    id: int
    student_id: Optional[str] = None
    request_type: str
    model_used: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    tools_used: Optional[list] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenUsageSummary(BaseModel):
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    by_type: dict = {}
    by_student: list = []


class AlertResponse(BaseModel):
    alert_type: str  # inactive_student, declining_rating, goal_completed
    message: str
    severity: str = "info"  # info, warning, success
    data: Optional[dict] = None


class LibrarianChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class LibrarianChatResponse(BaseModel):
    message: str
    session_id: str
    token_usage: Optional[dict] = None
    latency_ms: Optional[int] = None
    tools_used: Optional[list] = None
    model_used: Optional[str] = None


class GenreDistribution(BaseModel):
    genre: str
    count: int
    percentage: float
