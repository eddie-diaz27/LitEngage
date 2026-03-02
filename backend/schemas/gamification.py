"""Pydantic schemas for gamification features."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    rank: int
    student_id: str
    name: str
    score: float
    books_completed: int
    review_count: int
    current_streak: int


class BadgeResponse(BaseModel):
    id: int
    badge_type: str
    badge_name: str
    badge_level: int
    earned_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    streak_last_date: Optional[datetime] = None


class ReadingGoalResponse(BaseModel):
    id: int
    month: int
    year: int
    target_books: int
    books_completed: int
    progress_pct: float = 0.0

    model_config = {"from_attributes": True}


class ReadingGoalCreate(BaseModel):
    target_books: int = Field(..., ge=1, le=50)
