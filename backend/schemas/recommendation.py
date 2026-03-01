"""Pydantic schemas for recommendation-related requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationLogResponse(BaseModel):
    id: int
    student_id: str
    book_ids_json: Optional[List[str]] = None
    explanation: Optional[str] = None
    model_used: Optional[str] = None
    reading_level_filter: Optional[str] = None
    genres_searched: Optional[List[str]] = None
    feedback: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FeedbackRequest(BaseModel):
    feedback: str = Field(..., pattern="^(thumbs_up|thumbs_down)$")


class AnalyticsResponse(BaseModel):
    total_recommendations: int
    recommendations_this_week: int
    thumbs_up: int
    thumbs_down: int
    active_students_this_week: int
    total_books: int = 0
    total_students: int = 0
