"""Pydantic schemas for student-related requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    name: str
    grade_level: int = Field(..., ge=1, le=12)
    reading_level: str
    preferences_json: Optional[dict] = None


class StudentCreate(StudentBase):
    pass


class StudentResponse(StudentBase):
    id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    current_streak: int = 0
    longest_streak: int = 0

    model_config = {"from_attributes": True}


class StudentPreferencesUpdate(BaseModel):
    preferences_json: dict


class ReadingHistoryResponse(BaseModel):
    id: int
    book_id: str
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    book_author_name: Optional[str] = None
    book_image_url: Optional[str] = None
    book_genres: Optional[list] = None
    book_avg_rating: Optional[float] = None
    status: str
    rating: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ReadingHistoryCreate(BaseModel):
    book_id: str
    status: str = Field(..., pattern="^(wishlist|reading|completed|abandoned)$")


class ReadingHistoryUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(wishlist|reading|completed|abandoned)$")
    rating: Optional[int] = Field(None, ge=1, le=5)


class StudentListResponse(BaseModel):
    id: str
    name: str
    grade_level: int
    reading_level: str

    model_config = {"from_attributes": True}


class StudentProfileResponse(BaseModel):
    """Full student profile with stats."""
    id: str
    name: str
    grade_level: int
    reading_level: str
    preferences_json: Optional[dict] = None
    current_streak: int = 0
    longest_streak: int = 0
    books_completed: int = 0
    books_reading: int = 0
    books_wishlist: int = 0
    review_count: int = 0
    badge_count: int = 0
